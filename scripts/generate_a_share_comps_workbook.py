#!/usr/bin/env python3
"""Generate a minimal XLSX comps workbook from A-share comps artifacts."""

from __future__ import annotations

import argparse
import csv
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SHEETS = [
    ("Comps Main", "comps_main.csv"),
    ("Source Notes", "comps_source_notes.csv"),
    ("Exceptions", "comps_exceptions.csv"),
    ("Statistics", "comps_statistics.csv"),
    ("Data Gaps", "comps_data_gaps.csv"),
    ("Summary", "comps_summary.md"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comps-dir", required=True, help="Directory containing phase 5 comps artifacts.")
    parser.add_argument("--output", required=True, help="Path to the XLSX workbook to write.")
    parser.add_argument("--theme", required=True, help="Chinese theme name for the summary sheet title.")
    return parser.parse_args()


def read_csv(path: Path) -> list[list[str]]:
    if not path.is_file():
        return [["missing_file"], [path.name]]
    with path.open(newline="", encoding="utf-8") as handle:
        return [list(row) for row in csv.reader(handle)]


def read_markdown(path: Path, theme: str) -> list[list[str]]:
    rows = [["theme", theme], ["source_file", path.name], []]
    if not path.is_file():
        return rows + [["missing_file", path.name]]
    for line in path.read_text(encoding="utf-8").splitlines():
        rows.append([line])
    return rows


def column_name(index: int) -> str:
    name = ""
    current = index
    while current:
        current, remainder = divmod(current - 1, 26)
        name = chr(65 + remainder) + name
    return name


def sheet_xml(rows: list[list[str]]) -> str:
    row_xml: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{column_name(column_index)}{row_index}"
            text = escape(str(value))
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    body = "".join(row_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{body}</sheetData>"
        "</worksheet>"
    )


def workbook_xml(sheet_names: list[str]) -> str:
    sheets = []
    for index, name in enumerate(sheet_names, start=1):
        sheets.append(
            f'<sheet name="{escape(name)}" sheetId="{index}" '
            f'r:id="rId{index}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(sheets)}</sheets>'
        "</workbook>"
    )


def workbook_relationships_xml(sheet_count: int) -> str:
    rels = []
    for index in range(1, sheet_count + 1):
        rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(rels)}'
        "</Relationships>"
    )


def root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def content_types_xml(sheet_count: int) -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ]
    for index in range(1, sheet_count + 1):
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'{"".join(overrides)}'
        "</Types>"
    )


def load_sheet_rows(comps_dir: Path, theme: str) -> list[tuple[str, list[list[str]]]]:
    result = []
    for sheet_name, filename in SHEETS:
        path = comps_dir / filename
        if filename.endswith(".csv"):
            rows = read_csv(path)
        else:
            rows = read_markdown(path, theme)
        result.append((sheet_name, rows))
    return result


def write_workbook(output: Path, sheets: list[tuple[str, list[list[str]]]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", root_relationships_xml())
        archive.writestr("xl/workbook.xml", workbook_xml([name for name, _rows in sheets]))
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relationships_xml(len(sheets)))
        for index, (_name, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(rows))


def main() -> int:
    args = parse_args()
    comps_dir = Path(args.comps_dir)
    output = Path(args.output)
    sheets = load_sheet_rows(comps_dir, args.theme)
    write_workbook(output, sheets)
    print(f"wrote comps workbook: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
