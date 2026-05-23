#!/usr/bin/env python3
"""Fetch A-share index valuation data from AkShare."""

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
    parser.add_argument("--max-rows", type=int, default=30, help="Max rows per dataset.")
    return parser.parse_args()


def safe_str(value: Any) -> str:
    if value is None or str(value).strip() in ("", "-", "--", "nan", "None"):
        return MISSING
    return str(value)


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


def fetch_index_valuation(max_rows: int) -> list[dict[str, str]]:
    """Fetch CSIndex valuation data (PE, PB, dividend yield)."""
    import akshare as ak

    try:
        frame = ak.stock_zh_index_value_csindex(symbol="000300")
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-max_rows:]:
            rows.append({
                "index_code": "000300",
                "index_name": "沪深300",
                "date": safe_str(row.get("日期", row.get("date", ""))),
                "pe": safe_str(row.get("市盈率1", row.get("PE", ""))),
                "pb": safe_str(row.get("市净率", row.get("PB", ""))),
                "dividend_yield": safe_str(row.get("股息率1", row.get("股息率", ""))),
                "source_type": "official_statistics",
                "source_name": "AkShare stock_zh_index_value_csindex",
            })
        return rows
    except Exception:
        return []


def fetch_market_pe_pb() -> list[dict[str, str]]:
    """Fetch A-share market-wide PE and PB."""
    import akshare as ak

    rows = []
    try:
        pe_frame = ak.stock_a_ttm_lyr()
        pe_records = dataframe_to_records(pe_frame)
        if pe_records:
            latest = pe_records[-1]
            rows.append({
                "indicator": "A股整体PE_TTM",
                "date": safe_str(latest.get("日期", latest.get("date", ""))),
                "value": safe_str(latest.get("PE_TTM", latest.get("pe_ttm", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_a_ttm_lyr",
            })
    except Exception:
        pass

    try:
        pb_frame = ak.stock_a_all_pb()
        pb_records = dataframe_to_records(pb_frame)
        if pb_records:
            latest = pb_records[-1]
            rows.append({
                "indicator": "A股整体PB",
                "date": safe_str(latest.get("日期", latest.get("date", ""))),
                "value": safe_str(latest.get("PB", latest.get("pb", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_a_all_pb",
            })
    except Exception:
        pass

    return rows


def fetch_index_spot(max_rows: int) -> list[dict[str, str]]:
    """Fetch major index spot data."""
    import akshare as ak

    try:
        frame = ak.stock_zh_index_spot_em()
        records = dataframe_to_records(frame)
        rows = []
        major_indices = {"000001", "399001", "399006", "000300", "000016", "000905", "000852"}
        for row in records:
            code = safe_str(row.get("代码", ""))
            if code not in major_indices:
                continue
            rows.append({
                "index_code": code,
                "index_name": safe_str(row.get("名称", "")),
                "price": safe_str(row.get("最新价", "")),
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "amount": safe_str(row.get("成交额", "")),
                "pe": safe_str(row.get("市盈率", "")),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_zh_index_spot_em",
            })
            if len(rows) >= max_rows:
                break
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
    entries = [
        {
            "file": "index_valuation.csv",
            "source_type": "official_statistics",
            "source_name": "AkShare stock_zh_index_value_csindex",
            "period_or_basis": "指数估值历史 PE/PB/股息率",
            "missing_behavior": "指数估值写来源缺失",
        },
        {
            "file": "market_pe_pb.csv",
            "source_type": "public_market_data",
            "source_name": "AkShare stock_a_ttm_lyr, stock_a_all_pb",
            "period_or_basis": "A 股整体 PE/PB 最新可用期",
            "missing_behavior": "市场整体估值写来源缺失",
        },
        {
            "file": "index_spot.csv",
            "source_type": "public_market_data",
            "source_name": "AkShare stock_zh_index_spot_em",
            "period_or_basis": "主要指数实时行情",
            "missing_behavior": "指数行情写来源缺失",
        },
    ]
    for entry in entries:
        has_entry = any(item.get("file") == entry["file"] for item in files)
        if has_entry:
            continue
        files.append({
            **entry,
            "data_time": as_of,
            "verification_status": "verified",
        })
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_val = fetch_index_valuation(args.max_rows)
    market_pe_pb = fetch_market_pe_pb()
    index_spot = fetch_index_spot(args.max_rows)

    # Write index valuation history
    val_cols = ["index_code", "index_name", "date", "pe", "pb", "dividend_yield", "source_type", "source_name"]
    write_csv(output_dir / "index_valuation.csv", index_val, val_cols)

    # Write market PE/PB
    mp_cols = ["indicator", "date", "value", "source_type", "source_name"]
    write_csv(output_dir / "market_pe_pb.csv", market_pe_pb, mp_cols)

    # Write index spot
    spot_cols = ["index_code", "index_name", "price", "change_pct", "amount", "pe", "source_type", "source_name"]
    write_csv(output_dir / "index_spot.csv", index_spot, spot_cols)

    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote index valuation: {len(index_val)} valuation, {len(market_pe_pb)} market PE/PB, {len(index_spot)} index spot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
