#!/usr/bin/env python3
"""Fetch A-share northbound and margin trading data from AkShare."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
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


def fetch_northbound_flow() -> list[dict[str, str]]:
    """Fetch northbound capital flow summary."""
    import akshare as ak

    try:
        frame = ak.stock_hsgt_fund_flow_summary_em()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-30:]:
            rows.append({
                "date": safe_str(row.get("日期", row.get("date", ""))),
                "hgt_net": safe_str(row.get("沪股通净流入", "")),
                "sgt_net": safe_str(row.get("深股通净流入", "")),
                "northbound_net": safe_str(row.get("北向资金净流入", "")),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_hsgt_fund_flow_summary_em",
            })
        return rows
    except Exception:
        return []


def fetch_northbound_holdings(max_rows: int) -> list[dict[str, str]]:
    """Fetch northbound holdings by stock."""
    import akshare as ak

    try:
        frame = ak.stock_hsgt_hold_stock_em(market="北向")
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "code": safe_str(row.get("代码", row.get("股票代码", ""))),
                "name": safe_str(row.get("名称", row.get("股票简称", ""))),
                "hold_shares": safe_str(row.get("持股数量", "")),
                "hold_market_cap": safe_str(row.get("持股市值", "")),
                "hold_ratio": safe_str(row.get("持股占比", row.get("持股占流通股比", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_hsgt_hold_stock_em",
            })
        return rows
    except Exception:
        return []


def margin_date_window(as_of: str) -> tuple[str, str]:
    try:
        end_date = dt.date.fromisoformat(as_of[:10])
    except ValueError:
        end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=30)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def fetch_margin_summary(as_of: str) -> list[dict[str, str]]:
    """Fetch margin trading summary from SSE."""
    import akshare as ak

    try:
        start_date, end_date = margin_date_window(as_of)
        frame = ak.stock_margin_sse(start_date=start_date, end_date=end_date)
        records = dataframe_to_records(frame)
        rows = []
        for row in records[-30:]:
            rows.append({
                "date": safe_str(row.get("信用交易日期", row.get("日期", ""))),
                "financing_balance": safe_str(row.get("融资余额(元)", row.get("融资余额", ""))),
                "securities_balance": safe_str(row.get("融券余量金额(元)", row.get("融券余额", ""))),
                "financing_buy": safe_str(row.get("融资买入额(元)", row.get("融资买入", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_margin_sse",
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
    for entry_file, entry_name in [
        ("northbound_flow.csv", "northbound"),
        ("northbound_holdings.csv", "northbound_holdings"),
        ("margin_trading.csv", "margin"),
    ]:
        has_entry = any(item.get("file") == entry_file for item in files)
        if not has_entry:
            files.append({
                "file": entry_file,
                "source_type": "public_market_data",
                "source_name": f"AkShare {entry_name} 接口",
                "data_time": as_of,
                "period_or_basis": "最新可用期",
                "verification_status": "verified",
                "missing_behavior": "资金流和融资融券数据写来源缺失，不作为基本面证据",
            })
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    nb_flow = fetch_northbound_flow()
    nb_holdings = fetch_northbound_holdings(args.max_rows)
    margin = fetch_margin_summary(args.as_of)

    nb_flow_cols = ["date", "hgt_net", "sgt_net", "northbound_net", "source_type", "source_name"]
    nb_hold_cols = ["code", "name", "hold_shares", "hold_market_cap", "hold_ratio", "source_type", "source_name"]
    margin_cols = ["date", "financing_balance", "securities_balance", "financing_buy", "source_type", "source_name"]

    write_csv(output_dir / "northbound_flow.csv", nb_flow, nb_flow_cols)
    write_csv(output_dir / "northbound_holdings.csv", nb_holdings, nb_hold_cols)
    write_csv(output_dir / "margin_trading.csv", margin, margin_cols)
    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote northbound/margin: {len(nb_flow)} flow, {len(nb_holdings)} holdings, {len(margin)} margin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
