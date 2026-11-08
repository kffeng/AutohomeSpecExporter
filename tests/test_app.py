from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exporter import export_snapshot
from scraper import AutohomeError, FetchResult, extract_series_id, merge_payloads


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
