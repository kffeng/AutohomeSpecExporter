from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.request import Request as UrlRequest, urlopen

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.serving import make_server

from embedded_assets import WEB_ASSETS_B64
from exporter import export_snapshot, safe_filename
from scraper import AutohomeError, extract_series_id, scrape_series

APP_NAME = "汽车之家配置采集器"
APP_VERSION = "1.0.5"
DEFAULT_PORT = 8765
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="autohome-job")
SERVER = None


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def web_asset(filename: str) -> bytes:
    if filename not in WEB_ASSETS_B64:
        raise KeyError(filename)
    disk_path = resource_path("web") / filename
    if disk_path.is_file():
        return disk_path.read_bytes()
    return base64.b64decode(WEB_ASSETS_B64[filename])


def web_response(filename: str) -> Response:
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(web_asset(filename), mimetype=mime)


def app_data_dir() -> Path:
    configured = os.environ.get("AUTOHOME_APP_DATA")
    if configured:
        path = Path(configured)
    elif platform.system() == "Windows":
        path = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AutohomeSpecExporter"
    elif platform.system() == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "AutohomeSpecExporter"
    else:
        path = Path.home() / ".local" / "share" / "autohome-spec-exporter"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = app_data_dir()
CACHE_DIR = DATA_DIR / "cache"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = DATA_DIR / "logs"
for folder in (CACHE_DIR, EXPORT_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)


configure_logging()
logger = logging.getLogger(APP_NAME)


def cache_path(series_id: str) -> Path:
    return CACHE_DIR / f"{series_id}.json"


def load_cache(series_id: str) -> dict[str, Any] | None:
    path = cache_path(series_id)
    if not path.exists():
        return None
    try:
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        max_hours = float(os.environ.get("AUTOHOME_CACHE_HOURS", "12"))
        if age > timedelta(hours=max_hours):
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        logger.exception("读取缓存失败")
        return None


def save_cache(snapshot: dict[str, Any]) -> None:
    series_id = str(snapshot.get("series_id") or "")
    if not series_id:
        return
    path = cache_path(series_id)
    temp = path.with_suffix(".tmp")
    try:
        temp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
    except OSError:
        logger.exception("写入缓存失败")


def update_job(job_id: str, **changes: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is not None:
            job.update(changes)
            job["updated_at"] = datetime.now().isoformat(timespec="seconds")


def run_job(job_id: str, url: str, force_refresh: bool = False) -> None:
    try:
        update_job(job_id, status="running", progress=2, message="正在识别汽车之家车系")
        series_id = extract_series_id(url)
        snapshot = None if force_refresh else load_cache(series_id)
        if snapshot:
            update_job(job_id, progress=64, message="已读取本地缓存，正在整理预览")
        else:
            def progress(value: int, message: str) -> None:
                update_job(job_id, progress=value, message=message)

            snapshot = scrape_series(series_id, progress)
            save_cache(snapshot)

        update_job(job_id, progress=92, message="正在准备车型预览")
        variants = snapshot.get("variants") or []
        for variant in variants:
            variant["display_name"] = variant.get("specname") or variant.get("full_name")
        update_job(
            job_id,
            status="completed",
            progress=100,
            message="抓取完成，可以导出 Excel",
            snapshot=snapshot,
            series_id=series_id,
            series_name=snapshot.get("series_name"),
            stats=snapshot.get("stats"),
            years=snapshot.get("years"),
            variants=variants,
            warnings=snapshot.get("warnings") or [],
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )
        logger.info("任务完成 series=%s variants=%s", series_id, len(variants))
    except Exception as exc:
        logger.exception("任务失败")
        message = str(exc) if isinstance(exc, AutohomeError) else "程序处理失败，请查看日志后重试。"
        update_job(
            job_id,
            status="error",
            progress=100,
            message=message,
            error=message,
            completed_at=datetime.now().isoformat(timespec="seconds"),
        )


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "status",
        "progress",
        "message",
        "error",
        "series_id",
        "series_name",
        "stats",
        "years",
        "variants",
        "warnings",
        "created_at",
        "updated_at",
        "completed_at",
    )
    return {key: job.get(key) for key in keys}


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    @app.after_request
    def add_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return web_response("index.html")

    @app.get("/favicon.svg")
    @app.get("/favicon.ico")
    def favicon():
        return web_response("favicon.svg")

    @app.get("/static/<path:filename>")
    def static_asset(filename: str):
        try:
            return web_response(filename)
        except KeyError:
            return Response("Not Found", status=404, mimetype="text/plain")

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, name=APP_NAME, version=APP_VERSION)

    @app.get("/api/app-info")
    def app_info():
        return jsonify(name=APP_NAME, version=APP_VERSION, data_dir=str(DATA_DIR))

    @app.post("/api/jobs")
    def create_job():
        body = request.get_json(silent=True) or {}
        url = str(body.get("url") or "").strip()
        if not url:
            return jsonify(error="请输入汽车之家车系网址。"), 400
        try:
            series_id = extract_series_id(url)
        except AutohomeError as exc:
            return jsonify(error=str(exc)), 400

        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "url": url,
            "series_id": series_id,
            "status": "queued",
            "progress": 0,
            "message": "任务已创建，等待处理",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        EXECUTOR.submit(run_job, job_id, url, bool(body.get("force_refresh")))
        return jsonify(job_id=job_id), 202

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                return jsonify(error="任务不存在或程序已重启。"), 404
            return jsonify(public_job(job))

    @app.get("/api/jobs/<job_id>/export")
    def export_job(job_id: str):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if job is None:
            return jsonify(error="任务不存在。"), 404
        if job.get("status") != "completed":
            return jsonify(error="任务尚未完成。"), 409
        snapshot = job.get("snapshot")
        if not snapshot:
            return jsonify(error="没有可导出的数据。"), 404
        try:
            path = export_snapshot(snapshot, EXPORT_DIR)
        except Exception:
            logger.exception("导出 Excel 失败")
            return jsonify(error="生成 Excel 失败，请稍后重试。"), 500
        return send_file(
            path,
            as_attachment=True,
            download_name=path.name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.post("/api/open-export-folder")
    def open_export_folder():
        try:
            if platform.system() == "Windows":
                os.startfile(str(EXPORT_DIR))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(EXPORT_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(EXPORT_DIR)])
            return jsonify(ok=True)
        except Exception:
            logger.exception("打开导出目录失败")
            return jsonify(error="无法打开导出目录。"), 500

    @app.post("/api/shutdown")
    def shutdown_app():
        def stop_later():
            time.sleep(0.25)
            if SERVER is not None:
                SERVER.shutdown()
            (DATA_DIR / "runtime_port.txt").unlink(missing_ok=True)

        threading.Thread(target=stop_later, daemon=True).start()
        return jsonify(ok=True)

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify(error="接口不存在。"), 404
        try:
            return web_response("index.html")
        except KeyError:
            return Response("页面资源缺失，请重新安装程序。", status=404, mimetype="text/plain")

    return app


def port_file() -> Path:
    return DATA_DIR / "runtime_port.txt"


def saved_port() -> int | None:
    try:
        return int(port_file().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def show_error_dialog(message: str) -> None:
    if platform.system() == "Windows":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
        except Exception:
            pass


def health_info(port: int) -> dict[str, Any] | None:
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.8) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))
            return data if data.get("name") == APP_NAME else None
    except Exception:
        return None


def root_ok(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/", timeout=1.2) as response:
            return response.status == 200
    except Exception:
        return False


def request_shutdown(port: int) -> None:
    try:
        request = UrlRequest(
            f"http://127.0.0.1:{port}/api/shutdown",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=1.5) as response:
            response.read()
    except Exception:
        logger.exception("通知旧版本退出失败")


def wait_until_down(port: int, timeout: float = 4.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if health_info(port) is None:
            return True
        time.sleep(0.15)
    return False


def find_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用的本地端口。")


def open_browser(url: str) -> None:
    webbrowser.open(url, new=1, autoraise=True)


def handle_existing_instance() -> bool:
    candidates: list[int] = []
    for candidate in (saved_port(), DEFAULT_PORT):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for port in candidates:
        info = health_info(port)
        if not info:
            continue
        version = str(info.get("version") or "")
        if version == APP_VERSION and root_ok(port):
            open_browser(f"http://127.0.0.1:{port}")
            return True

        logger.info("发现旧实例 version=%s port=%s，准备退出旧进程", version, port)
        request_shutdown(port)
        wait_until_down(port)
    return False


def main() -> int:
    global SERVER
    if handle_existing_instance():
        return 0
    try:
        port = find_port()
        app = create_app()
        SERVER = make_server("127.0.0.1", port, app, threaded=True)
        port_file().write_text(str(port), encoding="utf-8")
        url = f"http://127.0.0.1:{port}"
        threading.Timer(0.5, lambda: open_browser(url)).start()
        logger.info("启动 %s %s -> %s", APP_NAME, APP_VERSION, url)
        SERVER.serve_forever()
        return 0
    except Exception as exc:
        logger.exception("程序启动失败")
        show_error_dialog(f"程序启动失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
