from __future__ import annotations

import html
import json
import os
import re
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

API_URL = "https://car-web-m.autohome.com.cn/car/param/getParamConf"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0 Safari/537.36"
)
STATUS_LABELS = {10: "待售", 20: "在售", 30: "在售", 40: "停售"}
STATUS_ORDER = {20: 0, 30: 0, 40: 1, 10: 2}

ProgressCallback = Callable[[int, str], None]


class AutohomeError(RuntimeError):
    pass


@dataclass
class FetchResult:
    year: int | None
    payload: dict[str, Any]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", "", str(value))
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_series_id(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise AutohomeError("请输入汽车之家车系网址。")
    if raw.isdigit():
        return raw

    # 只解析汽车之家域名，避免把用户输入直接作为任意网络请求目标。
    candidate = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host and not (host == "autohome.com.cn" or host.endswith(".autohome.com.cn")):
        raise AutohomeError("只支持汽车之家 autohome.com.cn 的网址。")

    patterns = (
        r"(?:www|car|m)\.autohome\.com\.cn/config/series/(\d+)\.html",
        r"autohome\.com\.cn/(\d+)(?:/|$)",
        r"[?&]seriesid=(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            return match.group(1)
    raise AutohomeError("没有从网址中识别到车系 ID，请使用汽车之家车系的参数配置页网址。")


def _load_mock_payload(series_id: str, year: int | None) -> dict[str, Any] | None:
    mock_dir = os.environ.get("AUTOHOME_MOCK_DIR")
    if not mock_dir:
        return None
    path = Path(mock_dir) / (f"year_{year}.json" if year is not None else "default.json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _request_json(url: str, referer: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Origin": "https://car.m.autohome.com.cn",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close",
        },
    )
    context = ssl.create_default_context()
    with urlopen(request, timeout=25, context=context) as response:
        raw = response.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AutohomeError("汽车之家返回的数据格式异常，请稍后重试。") from exc


def fetch_payload(
    series_id: str,
    year: int | None = None,
    *,
    unsale: bool = False,
    retries: int = 3,
) -> dict[str, Any]:
    mock = _load_mock_payload(series_id, year)
    if mock is not None:
        return mock

    params: dict[str, Any] = {"site": 1, "seriesid": series_id}
    if year is not None:
        params["year"] = year
        if unsale:
            params["unsale"] = "true"
    url = f"{API_URL}?{urlencode(params)}"
    referer = f"https://car.m.autohome.com.cn/config/series/{series_id}.html"

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            payload = _request_json(url, referer)
            if payload.get("returncode") not in (0, "0"):
                raise AutohomeError(
                    str(payload.get("message") or f"接口错误：{payload.get('returncode')}")
                )
            return payload
        except (HTTPError, URLError, TimeoutError, AutohomeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.8 * (attempt + 1))
    raise AutohomeError(f"连接汽车之家失败：{last_error}")


def _installed_years(payload: dict[str, Any]) -> list[int]:
    result = payload.get("result") or {}
    years: set[int] = set()
    for condition in result.get("conditionlist") or []:
        for item in condition.get("list") or []:
            match = re.search(r"(\d{4})款", clean_text(item.get("name")))
            if match:
                years.add(int(match.group(1)))
    for spec in (result.get("specinfo") or {}).get("specitems") or []:
        try:
            year = int(spec.get("year"))
        except (TypeError, ValueError):
            year = None
        if year:
            years.add(year)
    current_year = datetime.now().year
    return sorted((year for year in years if 2000 <= year <= current_year + 2), reverse=True)


def _years_to_query(payload: dict[str, Any]) -> list[int]:
    """默认页面已经带停售车型的年份不再重复查询隐藏停售页。"""
    result = payload.get("result") or {}
    years = _installed_years(payload)
    stop_years: set[int] = set()
    for spec in (result.get("specinfo") or {}).get("specitems") or []:
        try:
            status = int(spec.get("specstatus", 0))
            year = int(spec.get("year"))
        except (TypeError, ValueError):
            continue
        if status == 40:
            stop_years.add(year)
    return [year for year in years if year not in stop_years]


def format_cell(model: dict[str, Any]) -> str:
    if not model:
        return "-"

    parts: list[str] = []
    value = clean_text(model.get("value"))
    if value:
        parts.append(value)
    subvalue = clean_text(model.get("subvalue"))
    if subvalue and subvalue not in parts:
        parts.append(subvalue)

    color_names = [
        clean_text(item.get("name"))
        for item in ((model.get("colorinfo") or {}).get("list") or [])
        if clean_text(item.get("name"))
    ]
    if color_names:
        parts.append("、".join(dict.fromkeys(color_names)))

    options: list[str] = []
    for sub in model.get("sublist") or []:
        name = clean_text(sub.get("name"))
        marker = clean_text(sub.get("value"))
        price = clean_text(sub.get("priceinfo"))
        if marker == "●":
            text = name
        elif marker == "○":
            text = f"○ {name}".strip()
        elif marker == "-":
            text = "-"
        else:
            text = f"{marker}{name}".strip()
        if price:
            text = f"{text}（{price}）" if text else f"（{price}）"
        if text and text not in options:
            options.append(text)
    if options:
        parts.append("、".join(options))

    deduped: list[str] = []
    for part in parts:
        if part and part not in deduped:
            deduped.append(part)
    return "；".join(deduped) if deduped else "-"


def _infer_series_name(variants: list[dict[str, Any]]) -> str:
    for variant in variants:
        full_name = clean_text(variant.get("full_name"))
        match = re.match(r"^(.*?)\s+\d{4}款(?:\s|$)", full_name)
        if match and match.group(1):
            return match.group(1).strip()
    return "汽车之家车系"


def merge_payloads(fetches: list[FetchResult], warnings: list[str] | None = None) -> dict[str, Any]:
    variants_by_id: dict[int, dict[str, Any]] = {}
    group_order: list[tuple[str, str]] = []
    group_items: dict[tuple[str, str], list[tuple[tuple[str, Any], dict[str, Any]]]] = {}

    for fetch in fetches:
        result = fetch.payload.get("result") or {}
        for spec in (result.get("specinfo") or {}).get("specitems") or []:
            try:
                spec_id = int(spec["specid"])
                status = int(spec.get("specstatus", 0))
            except (KeyError, TypeError, ValueError):
                continue
            if status not in (20, 30, 40):
                continue
            year = spec.get("year") or fetch.year
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = 0
            variants_by_id[spec_id] = {
                "specid": spec_id,
                "specname": clean_text(spec.get("specname")),
                "full_name": "",
                "year": year,
                "status": status,
                "status_label": STATUS_LABELS.get(status, str(status)),
                "guide_price": clean_text(spec.get("minprice")),
                "discount": clean_text(spec.get("downprice")),
                "price_type": clean_text(spec.get("pricetitle")),
                "condition": spec.get("condition") or [],
            }

        for group in (result.get("paramitems") or []) + (result.get("configitems") or []):
            group_name = clean_text(group.get("groupname"))
            category = clean_text(group.get("itemtype"))
            group_key = (group_name, category)
            if group_key not in group_items:
                group_items[group_key] = []
                group_order.append(group_key)
            existing = {key: item for key, item in group_items[group_key]}
            for item in group.get("items") or []:
                name = clean_text(item.get("name"))
                if not name:
                    continue
                param_id = item.get("paramitemid", 0)
                item_key = (name, param_id)
                if item_key not in existing:
                    record = {
                        "name": name,
                        "paramitemid": param_id,
                        "values": {},
                    }
                    group_items[group_key].append((item_key, record))
                    existing[item_key] = record
                record = existing[item_key]
                for model in item.get("modelexcessids") or []:
                    try:
                        spec_id = int(model.get("id"))
                    except (TypeError, ValueError):
                        continue
                    if spec_id not in variants_by_id:
                        continue
                    if name == "车型名称":
                        variants_by_id[spec_id]["full_name"] = clean_text(model.get("value"))
                    record["values"][str(spec_id)] = format_cell(model)

    variants = list(variants_by_id.values())
    variants.sort(key=lambda item: (STATUS_ORDER.get(item["status"], 9), -item["year"], item["specid"]))
    for spec in (fetches[0].payload.get("result", {}).get("specinfo", {}).get("specitems", []) if fetches else []):
        try:
            spec_id = int(spec.get("specid"))
        except (TypeError, ValueError):
            continue
        if spec_id in variants_by_id and not variants_by_id[spec_id]["full_name"]:
            variants_by_id[spec_id]["full_name"] = clean_text(spec.get("specname"))

    params: list[dict[str, Any]] = []
    for group_key in group_order:
        group_name, category = group_key
        for _, record in group_items[group_key]:
            if not any(value not in ("", "-") for value in record["values"].values()):
                continue
            params.append(
                {
                    "group": group_name,
                    "category": category,
                    "name": record["name"],
                    "values": record["values"],
                }
            )

    onsale = sum(1 for variant in variants if variant["status"] in (20, 30))
    stopsale = sum(1 for variant in variants if variant["status"] == 40)
    years = sorted({variant["year"] for variant in variants if variant["year"]}, reverse=True)
    series_name = _infer_series_name(variants)
    series_id = fetches[0].payload.get("result", {}).get("seriesid") if fetches else ""
    return {
        "version": 1,
        "series_id": series_id,
        "series_name": series_name,
        "source_url": (
            f"https://car.m.autohome.com.cn/config/series/{series_id}.html"
            if series_id
            else ""
        ),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "variants": variants,
        "params": params,
        "years": years,
        "stats": {
            "onsale": onsale,
            "stopsale": stopsale,
            "variants": len(variants),
            "params": len(params),
            "years": len(years),
            "groups": len(group_order),
        },
        "warnings": warnings or [],
    }


def scrape_series(series_id: str, progress: ProgressCallback | None = None) -> dict[str, Any]:
    def report(value: int, message: str) -> None:
        if progress:
            progress(max(0, min(100, value)), message)

    report(4, "正在读取当前在售车型")
    default_payload = fetch_payload(series_id)
    default_result = default_payload.get("result") or {}
    if not (default_result.get("specinfo") or {}).get("specitems"):
        raise AutohomeError("汽车之家没有返回车型数据，请确认网址是否正确。")

    years = _years_to_query(default_payload)
    fetches = [FetchResult(None, default_payload)]
    warnings: list[str] = []
    if years:
        span = 62
        for index, year in enumerate(years, start=1):
            report(12 + int(span * (index - 1) / len(years)), f"正在补全 {year} 款停售车型")
            try:
                payload = fetch_payload(series_id, year, unsale=True)
                fetches.append(FetchResult(year, payload))
            except AutohomeError as exc:
                warnings.append(f"{year} 款读取失败：{exc}")
        report(78, "正在合并车款和配置项")
    else:
        report(64, "正在整理配置数据")

    report(84, "正在生成车型索引")
    snapshot = merge_payloads(fetches, warnings)
    snapshot["series_id"] = series_id
    snapshot["source_url"] = f"https://car.m.autohome.com.cn/config/series/{series_id}.html"
    report(100, "抓取完成")
    return snapshot
