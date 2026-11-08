from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

MAX_VARIANTS_PER_SHEET = 24
FONT = "Microsoft YaHei"
INK = "1F2937"
MUTED = "6B7280"
NAVY = "173B57"
BLUE = "2F75B5"
LIGHT_RULE = "D9E2F3"
GROUP_FILLS = {
    "参数信息": "EAF2F8",
    "安全配置": "FCE4D6",
    "操控配置": "FFF2CC",
    "智能/辅助驾驶": "E2F0D9",
    "外部配置": "DDEBF7",
    "内部配置": "EDE7F6",
    "个性化": "F2F2F2",
}




def _suppress_number_text_warnings(path: Path) -> None:
    """让 Excel 不把“506”“0.25”这类参数值标记为绿色小三角。"""
    temp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(
        temp, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", item.filename):
                if b"<ignoredErrors" not in content:
                    dimension = re.search(rb'<dimension ref="([^"]+)"', content)
                    sqref = dimension.group(1).decode("utf-8") if dimension else "A1:Z10000"
                    ignored = (
                        f'<ignoredErrors><ignoredError sqref="{sqref}" '
                        'numberStoredAsText="1"/></ignoredErrors>'
                    ).encode("utf-8")
                    positions = [
                        content.find(marker)
                        for marker in (b"<drawing", b"<legacyDrawing", b"<tableParts", b"<extLst")
                    ]
                    positions = [value for value in positions if value >= 0]
                    index = min(positions) if positions else content.rfind(b"</worksheet>")
                    content = content[:index] + ignored + content[index:]
            target.writestr(item, content)
    os.replace(temp, path)

def safe_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return value or "汽车之家配置表"


def _safe_sheet_name(value: str, used: set[str]) -> str:
    base = re.sub(r"[\\/*?:\[\]]+", "-", value).strip()[:31] or "配置表"
    name = base
    index = 2
    while name in used:
        suffix = f"({index})"
        name = f"{base[: 31 - len(suffix)]}{suffix}"
        index += 1
    used.add(name)
    return name


def _apply_title(sheet, title: str, subtitle: str, last_col: int) -> None:
    last_letter = get_column_letter(last_col)
    sheet.merge_cells(f"A1:{last_letter}1")
    sheet["A1"] = title
    sheet["A1"].font = Font(name=FONT, size=16, bold=True, color=INK)
    sheet["A1"].alignment = Alignment(horizontal="left", vertical="center")
    sheet.row_dimensions[1].height = 32

    sheet.merge_cells(f"A2:{last_letter}2")
    sheet["A2"] = subtitle
    sheet["A2"].font = Font(name=FONT, size=9, italic=True, color=MUTED)
    sheet["A2"].alignment = Alignment(horizontal="left", vertical="center")
    sheet.row_dimensions[2].height = 22


def _style_header(sheet, row: int, columns: int) -> None:
    for col in range(1, columns + 1):
        cell = sheet.cell(row=row, column=col)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(
            left=Side(style="thin", color="FFFFFF"),
            right=Side(style="thin", color="FFFFFF"),
        )
    sheet.row_dimensions[row].height = 40


def _add_table(sheet, ref: str, name: str) -> None:
    table = Table(displayName=name, ref=ref)
    style = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    table.tableStyleInfo = style
    sheet.add_table(table)


def _setup_print(sheet, last_col: int, last_row: int, header_row: int) -> None:
    sheet.freeze_panes = f"D{header_row + 1}"
    sheet.sheet_view.showGridLines = False
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_title_rows = f"1:{header_row}"
    sheet.print_area = f"A1:{get_column_letter(last_col)}{last_row}"


def _status_fill(status: int) -> str:
    return "E2F0D9" if status == 20 else "FCE4D6"


def _build_summary(
    workbook: Workbook,
    snapshot: dict[str, Any],
    sheet_links: dict[int, str],
    exported_at: datetime,
) -> None:
    sheet = workbook.active
    sheet.title = "车型清单"
    sheet.sheet_view.showGridLines = False
    headers = ["序号", "年款", "状态", "车款名称", "厂商指导价", "优惠金额", "价格类型", "配置工作表"]
    variants = snapshot["variants"]
    last_col = len(headers)
    last_row = 3 + len(variants)
    _apply_title(
        sheet,
        f"{snapshot['series_name']} 全量配置表",
        (
            f"来源：汽车之家  |  导出时间：{exported_at:%Y-%m-%d %H:%M:%S}  |  "
            f"在售 {snapshot['stats']['onsale']} 个  |  停售 {snapshot['stats']['stopsale']} 个  |  "
            "仅供参考，以官方及经销商实车为准"
        ),
        last_col,
    )
    for col_index, header in enumerate(headers, start=1):
        sheet.cell(row=3, column=col_index, value=header)
    _style_header(sheet, 3, last_col)

    for row_index, variant in enumerate(variants, start=4):
        link_sheet = sheet_links.get(variant["specid"], "")
        sheet.cell(row_index, 1, row_index - 3)
        sheet.cell(row_index, 2, f"{variant['year']}款")
        sheet.cell(row_index, 3, variant["status_label"])
        sheet.cell(row_index, 4, variant["specname"])
        sheet.cell(row_index, 5, variant["guide_price"] or "-")
        sheet.cell(row_index, 6, variant["discount"] or "-")
        sheet.cell(row_index, 7, variant["price_type"] or "-")
        sheet.cell(row_index, 8, link_sheet or "-")
        sheet.cell(row_index, 3).fill = PatternFill("solid", fgColor=_status_fill(variant["status"]))
        for col in range(1, last_col + 1):
            cell = sheet.cell(row_index, col)
            cell.font = Font(name=FONT, size=10, color=INK)
            cell.border = Border(bottom=Side(style="hair", color=LIGHT_RULE))
            cell.alignment = Alignment(
                horizontal="left" if col == 4 else "center",
                vertical="center",
                wrap_text=True,
            )
        sheet.row_dimensions[row_index].height = 28

    widths = [8, 10, 10, 42, 18, 16, 14, 22]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    _add_table(sheet, f"A3:H{last_row}", "VariantSummaryTable")
    sheet.freeze_panes = "A4"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True


def _build_config_sheet(
    workbook: Workbook,
    snapshot: dict[str, Any],
    variants: list[dict[str, Any]],
    title: str,
    sheet_name: str,
    exported_at: datetime,
    table_index: int,
) -> str:
    sheet = workbook.create_sheet(title=sheet_name)
    sheet.sheet_view.showGridLines = False
    spec_ids = [str(variant["specid"]) for variant in variants]
    variant_by_id = {str(variant["specid"]): variant for variant in variants}
    headers = ["参数组", "参数分类", "参数名称"] + [variant["specname"] for variant in variants]
    last_col = len(headers)
    rows: list[list[str]] = []
    for param in snapshot["params"]:
        values = [param["values"].get(spec_id, "-") for spec_id in spec_ids]
        if not any(value not in ("", "-") for value in values):
            continue
        rows.append([param["group"], param["category"], param["name"], *values])
    last_row = 3 + len(rows)

    subtitle = (
        f"来源：汽车之家  |  抓取时间：{snapshot['fetched_at'].replace('T', ' ')}  |  "
        f"年款：{variants[0]['year']}  |  状态：{variants[0]['status_label']}  |  "
        f"车款数：{len(variants)}  |  参数行数：{len(rows)}"
    )
    _apply_title(sheet, title, subtitle, last_col)
    for col_index, header in enumerate(headers, start=1):
        sheet.cell(row=3, column=col_index, value=header)
    _style_header(sheet, 3, last_col)

    current_group = None
    group_fill = "FFFFFF"
    for row_index, row in enumerate(rows, start=4):
        if row[0] != current_group:
            current_group = row[0]
            group_fill = GROUP_FILLS.get(current_group, "FFFFFF")
        for col_index, value in enumerate(row, start=1):
            cell = sheet.cell(row_index, col_index, value)
            cell.font = Font(name=FONT, size=10, color=INK)
            cell.alignment = Alignment(
                horizontal="left" if col_index <= 3 else "center",
                vertical="top",
                wrap_text=True,
            )
            if col_index <= 3:
                cell.fill = PatternFill("solid", fgColor=group_fill)
                cell.border = Border(
                    right=Side(style="thin", color=LIGHT_RULE),
                    bottom=Side(style="hair", color=LIGHT_RULE),
                )
            else:
                cell.border = Border(bottom=Side(style="hair", color=LIGHT_RULE))
        sheet.row_dimensions[row_index].height = 28

    fixed_widths = {1: 14, 2: 16, 3: 30}
    for col_index in range(1, last_col + 1):
        sheet.column_dimensions[get_column_letter(col_index)].width = fixed_widths.get(col_index, 24)

    _add_table(sheet, f"A3:{get_column_letter(last_col)}{last_row}", f"ConfigTable{table_index}")
    _setup_print(sheet, last_col, last_row, 3)
    return sheet.title


def _build_info_sheet(
    workbook: Workbook,
    snapshot: dict[str, Any],
    exported_at: datetime,
    sheet_names: Iterable[str],
) -> None:
    sheet = workbook.create_sheet(title="数据说明")
    sheet.sheet_view.showGridLines = False
    sheet.merge_cells("A1:B1")
    sheet["A1"] = "数据说明"
    sheet["A1"].font = Font(name=FONT, size=16, bold=True, color=INK)
    sheet["A1"].alignment = Alignment(horizontal="left", vertical="center")
    sheet.row_dimensions[1].height = 32

    rows = [
        ("车系名称", snapshot["series_name"]),
        ("车系 ID", snapshot["series_id"]),
        ("来源页面", snapshot["source_url"]),
        ("抓取时间", snapshot["fetched_at"].replace("T", " ")),
        ("导出时间", exported_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("在售车款", snapshot["stats"]["onsale"]),
        ("停售车款", snapshot["stats"]["stopsale"]),
        ("车款总数", snapshot["stats"]["variants"]),
        ("参数行数", snapshot["stats"]["params"]),
        ("年份数量", snapshot["stats"]["years"]),
        ("配置工作表", "、".join(sheet_names)),
        ("符号说明", "● 标配；○ 选配；- 无或暂无数据"),
        ("声明", "本表来自汽车之家公开页面，仅作信息整理参考，请以官方及经销商实际配置为准。"),
    ]
    if snapshot.get("warnings"):
        rows.append(("抓取提示", "；".join(snapshot["warnings"])))

    for row_index, (key, value) in enumerate(rows, start=3):
        key_cell = sheet.cell(row_index, 1, key)
        value_cell = sheet.cell(row_index, 2, value)
        key_cell.font = Font(name=FONT, size=10, bold=True, color=INK)
        key_cell.fill = PatternFill("solid", fgColor="EAF2F8")
        key_cell.alignment = Alignment(vertical="top")
        value_cell.font = Font(name=FONT, size=10, color=INK)
        value_cell.alignment = Alignment(vertical="top", wrap_text=True)
        sheet.row_dimensions[row_index].height = 27
    sheet.row_dimensions[3 + len(rows) - 1].height = 52
    sheet.column_dimensions["A"].width = 18
    sheet.column_dimensions["B"].width = 90


def export_snapshot(snapshot: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now()
    filename = (
        f"{safe_filename(snapshot['series_name'])}_"
        f"{exported_at:%Y%m%d_%H%M%S}_全量配置表.xlsx"
    )
    output_path = output_dir / filename

    workbook = Workbook()
    workbook.properties.title = f"{snapshot['series_name']} 全量配置表"
    workbook.properties.subject = "汽车之家在售及停售车型参数配置"
    workbook.properties.creator = "汽车之家配置采集器"
    workbook.properties.description = "数据来自汽车之家公开参数配置页面，仅供信息整理参考。"

    used_names: set[str] = {"车型清单", "数据说明"}
    sheet_links: dict[int, str] = {}
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for variant in snapshot["variants"]:
        groups.setdefault((variant["year"], variant["status"]), []).append(variant)
    ordered_groups = sorted(groups.items(), key=lambda item: (-item[0][0], 0 if item[0][1] == 20 else 1))

    config_sheets: list[str] = []
    table_index = 1
    for (year, status), variants in ordered_groups:
        status_label = "在售" if status == 20 else "停售"
        chunks = [variants[i : i + MAX_VARIANTS_PER_SHEET] for i in range(0, len(variants), MAX_VARIANTS_PER_SHEET)]
        for chunk_index, chunk in enumerate(chunks, start=1):
            suffix = f"-{chunk_index}" if len(chunks) > 1 else ""
            sheet_name = _safe_sheet_name(f"{year}{status_label}{suffix}", used_names)
            title = f"{snapshot['series_name']} {year}款 {status_label}配置"
            actual_name = _build_config_sheet(
                workbook,
                snapshot,
                chunk,
                title,
                sheet_name,
                exported_at,
                table_index,
            )
            table_index += 1
            config_sheets.append(actual_name)
            for variant in chunk:
                sheet_links[variant["specid"]] = actual_name

    _build_summary(workbook, snapshot, sheet_links, exported_at)
    _build_info_sheet(workbook, snapshot, exported_at, config_sheets)
    workbook.save(output_path)
    _suppress_number_text_warnings(output_path)
    return output_path
