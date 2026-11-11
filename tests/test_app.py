from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exporter import export_snapshot
from scraper import AutohomeError, FetchResult, _ssl_context, _years_to_query, extract_series_id, merge_payloads

TEST_DATA = tempfile.mkdtemp(prefix="autohome-exporter-tests-")
os.environ.setdefault("AUTOHOME_APP_DATA", TEST_DATA)
import main as app_main


class ScraperTests(unittest.TestCase):
    def test_extract_series_id_supports_common_urls(self) -> None:
        examples = {
            "https://www.autohome.com.cn/config/series/8241.html#pvareaid=3454437": "8241",
            "https://car.autohome.com.cn/config/series/66.html": "66",
            "https://www.autohome.com.cn/6962/": "6962",
            "8241": "8241",
        }
        for value, expected in examples.items():
            self.assertEqual(extract_series_id(value), expected)

    def test_rejects_non_autohome_url(self) -> None:
        with self.assertRaises(AutohomeError):
            extract_series_id("https://example.com/config/series/8241.html")

    def test_merge_onsale_and_stopsale(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        default = json.loads((fixtures / "q05_default.json").read_text(encoding="utf-8"))
        stopped = json.loads((fixtures / "q05_2026.json").read_text(encoding="utf-8"))
        snapshot = merge_payloads(
            [FetchResult(None, default), FetchResult(2026, stopped)]
        )
        self.assertEqual(snapshot["series_name"], "长安启源Q05")
        self.assertEqual(snapshot["stats"]["onsale"], 7)
        self.assertEqual(snapshot["stats"]["stopsale"], 7)
        self.assertEqual(snapshot["stats"]["variants"], 14)
        self.assertEqual(snapshot["years"], [2027, 2026])


class StatusThirtyTests(unittest.TestCase):
    def test_status_thirty_is_onsale_and_forty_is_stopsale(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        default = json.loads((fixtures / "a06_default.json").read_text(encoding="utf-8"))
        stopped = json.loads((fixtures / "a06_2026.json").read_text(encoding="utf-8"))
        self.assertEqual(_years_to_query(default), [2027, 2026])
        default_snapshot = merge_payloads([FetchResult(None, default)])
        self.assertEqual(default_snapshot["stats"]["onsale"], 16)
        self.assertEqual(default_snapshot["stats"]["stopsale"], 0)
        self.assertEqual(default_snapshot["stats"]["variants"], 16)
        snapshot = merge_payloads(
            [FetchResult(None, default), FetchResult(2026, stopped)]
        )
        self.assertEqual(snapshot["series_name"], "长安启源A06")
        self.assertEqual(snapshot["stats"]["onsale"], 16)
        self.assertEqual(snapshot["stats"]["stopsale"], 1)
        self.assertEqual(snapshot["stats"]["variants"], 17)
        statuses = {variant["specid"]: variant["status_label"] for variant in snapshot["variants"]}
        self.assertEqual(statuses[77262], "在售")
        self.assertEqual(statuses[72997], "停售")
        self.assertEqual(statuses[79411], "在售")
        with tempfile.TemporaryDirectory() as temp_dir:
            output = export_snapshot(snapshot, Path(temp_dir))
            from openpyxl import load_workbook

            workbook = load_workbook(output, data_only=True)
            self.assertIn("2027在售", workbook.sheetnames)
            self.assertIn("2026在售", workbook.sheetnames)
            self.assertIn("2026停售", workbook.sheetnames)
            self.assertEqual(workbook["2026在售"].max_column, 13)
            self.assertEqual(workbook["2026停售"].max_column, 4)


class AppAssetTests(unittest.TestCase):
    def test_web_assets_work_without_disk_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(app_main, "resource_path", return_value=Path(temp_dir)):
                html = app_main.web_asset("index.html").decode("utf-8")
                css = app_main.web_asset("styles.css").decode("utf-8")
        self.assertIn("汽车之家配置采集器", html)
        self.assertIn("--blue", css)

    def test_flask_serves_embedded_page(self) -> None:
        client = app_main.create_app().test_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/static/styles.css").status_code, 200)
        self.assertEqual(client.get("/static/app.js").status_code, 200)
        self.assertEqual(client.get("/favicon.ico").status_code, 200)

    def test_ssl_context_has_trusted_certificates(self) -> None:
        stats = _ssl_context().cert_store_stats()
        self.assertGreater(stats.get("x509_ca", 0), 0)

    def test_old_version_is_shut_down(self) -> None:
        old_health = {"name": app_main.APP_NAME, "version": "1.0.0"}
        with patch.object(app_main, "saved_port", return_value=8765), patch.object(
            app_main, "health_info", return_value=old_health
        ), patch.object(app_main, "request_shutdown") as shutdown, patch.object(
            app_main, "wait_until_down", return_value=True
        ):
            self.assertFalse(app_main.handle_existing_instance())
            shutdown.assert_called_once_with(8765)


class ExporterTests(unittest.TestCase):
    def test_export_workbook(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        default = json.loads((fixtures / "q05_default.json").read_text(encoding="utf-8"))
        stopped = json.loads((fixtures / "q05_2026.json").read_text(encoding="utf-8"))
        snapshot = merge_payloads(
            [FetchResult(None, default), FetchResult(2026, stopped)]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = export_snapshot(snapshot, Path(temp_dir))
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 20_000)

            from openpyxl import load_workbook

            workbook = load_workbook(output, data_only=True)
            self.assertEqual(workbook.sheetnames[0], "车型清单")
            self.assertIn("2027在售", workbook.sheetnames)
            self.assertIn("2026在售", workbook.sheetnames)
            self.assertIn("2026停售", workbook.sheetnames)
            self.assertEqual(workbook.sheetnames[-1], "数据说明")
            summary = workbook["车型清单"]
            self.assertIn("全量配置表", summary["A1"].value)
            self.assertEqual(summary["A3"].value, "序号")
            config = workbook["2026停售"]
            self.assertEqual(config["A3"].value, "参数组")
            self.assertEqual(config.freeze_panes, "D4")
            self.assertTrue(config.tables)


if __name__ == "__main__":
    unittest.main()
