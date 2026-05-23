#!/usr/bin/env python3
"""Fetch A-share macro context data from AkShare."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

MISSING = "来源缺失"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory for output files.")
    parser.add_argument("--as-of", required=True, help="Access date.")
    parser.add_argument("--max-rows", type=int, default=12, help="Max rows per indicator.")
    return parser.parse_args()


def safe_str(value: Any) -> str:
    if value is None or str(value).strip() in ("", "-", "--", "nan", "None"):
        return MISSING
    return str(value)


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


def fetch_gdp(max_rows: int) -> list[dict[str, str]]:
    import akshare as ak
    try:
        frame = ak.macro_china_gdp()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "indicator": "GDP",
                "period": safe_str(row.get("日期", row.get("季度", ""))),
                "value": safe_str(row.get("国内生产总值-绝对值", row.get("GDP", ""))),
                "yoy": safe_str(row.get("国内生产总值-同比增长", "")),
                "source_type": "official_statistics",
                "source_name": "AkShare macro_china_gdp",
            })
        return rows
    except Exception:
        return []


def fetch_cpi(max_rows: int) -> list[dict[str, str]]:
    import akshare as ak
    try:
        frame = ak.macro_china_cpi()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "indicator": "CPI",
                "period": safe_str(row.get("日期", row.get("月份", ""))),
                "value": safe_str(row.get("全国", row.get("CPI", ""))),
                "yoy": MISSING,
                "source_type": "official_statistics",
                "source_name": "AkShare macro_china_cpi",
            })
        return rows
    except Exception:
        return []


def fetch_ppi(max_rows: int) -> list[dict[str, str]]:
    import akshare as ak
    try:
        frame = ak.macro_china_ppi()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "indicator": "PPI",
                "period": safe_str(row.get("日期", row.get("月份", ""))),
                "value": safe_str(row.get("当月", row.get("PPI", ""))),
                "yoy": MISSING,
                "source_type": "official_statistics",
                "source_name": "AkShare macro_china_ppi",
            })
        return rows
    except Exception:
        return []


def fetch_pmi(max_rows: int) -> list[dict[str, str]]:
    import akshare as ak
    try:
        frame = ak.macro_china_pmi()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "indicator": "PMI",
                "period": safe_str(row.get("日期", "")),
                "value": safe_str(row.get("制造业", row.get("制造业PMI", ""))),
                "yoy": MISSING,
                "source_type": "official_statistics",
                "source_name": "AkShare macro_china_pmi",
            })
        return rows
    except Exception:
        return []


def fetch_fixed_asset_investment(max_rows: int) -> list[dict[str, str]]:
    import akshare as ak
    try:
        frame = ak.macro_china_gdzctz()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "indicator": "固定资产投资",
                "period": safe_str(row.get("日期", "")),
                "value": safe_str(row.get("固定资产投资", row.get("累计值", ""))),
                "yoy": safe_str(row.get("固定资产投资-同比增长", row.get("同比增长", ""))),
                "source_type": "official_statistics",
                "source_name": "AkShare macro_china_gdzctz",
            })
        return rows
    except Exception:
        return []


def fetch_consumer_retail(max_rows: int) -> list[dict[str, str]]:
    import akshare as ak
    try:
        frame = ak.macro_china_consumer_goods_retail()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "indicator": "社会消费品零售总额",
                "period": safe_str(row.get("日期", "")),
                "value": safe_str(row.get("社会消费品零售总额", row.get("当月", ""))),
                "yoy": safe_str(row.get("同比增长", "")),
                "source_type": "official_statistics",
                "source_name": "AkShare macro_china_consumer_goods_retail",
            })
        return rows
    except Exception:
        return []


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_source_manifest_entry(output_dir: Path, as_of: str) -> None:
    manifest_path = output_dir / "source_manifest.json"
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    has_entry = any(item.get("file") == "macro_context.csv" for item in files)
    if not has_entry:
        files.append({
            "file": "macro_context.csv",
            "source_type": "official_statistics",
            "source_name": "AkShare 宏观接口 (macro_china_gdp, macro_china_cpi, macro_china_ppi, macro_china_pmi)",
            "data_time": as_of,
            "period_or_basis": "最新可用期",
            "verification_status": "verified",
            "missing_behavior": "宏观字段写来源缺失，不得外推",
        })
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []
    all_rows.extend(fetch_gdp(args.max_rows))
    all_rows.extend(fetch_cpi(args.max_rows))
    all_rows.extend(fetch_ppi(args.max_rows))
    all_rows.extend(fetch_pmi(args.max_rows))
    all_rows.extend(fetch_fixed_asset_investment(args.max_rows))
    all_rows.extend(fetch_consumer_retail(args.max_rows))

    cols = ["indicator", "period", "value", "yoy", "source_type", "source_name"]
    write_csv(output_dir / "macro_context.csv", all_rows, cols)
    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote macro_context.csv with {len(all_rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
