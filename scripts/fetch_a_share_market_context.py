#!/usr/bin/env python3
"""Fetch A-share market context data from AkShare."""

from __future__ import annotations

import argparse
import csv
import json
import sys
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


def fetch_sector_fund_flow(max_rows: int) -> list[dict[str, str]]:
    """Fetch sector fund flow ranking."""
    import akshare as ak

    try:
        frame = ak.stock_sector_fund_flow_rank(indicator="今日")
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "name": safe_str(row.get("名称", "")),
                "change_pct": safe_str(row.get("今日涨跌幅", row.get("涨跌幅", ""))),
                "main_net_inflow": safe_str(row.get("今日主力净流入-净额", row.get("主力净流入-净额", ""))),
                "main_net_pct": safe_str(row.get("今日主力净流入-净占比", row.get("主力净流入-净占比", ""))),
                "super_large_net": safe_str(row.get("今日超大单净流入-净额", row.get("超大单净流入-净额", ""))),
                "large_net": safe_str(row.get("今日大单净流入-净额", row.get("大单净流入-净额", ""))),
                "medium_net": safe_str(row.get("今日中单净流入-净额", row.get("中单净流入-净额", ""))),
                "small_net": safe_str(row.get("今日小单净流入-净额", row.get("小单净流入-净额", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_sector_fund_flow_rank",
            })
        return rows
    except Exception:
        return []


def fetch_board_changes(max_rows: int) -> list[dict[str, str]]:
    """Fetch board change alerts."""
    import akshare as ak

    try:
        frame = ak.stock_board_change_em()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "board_name": safe_str(row.get("板块名称", row.get("名称", ""))),
                "board_type": safe_str(row.get("板块类型", "")),
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "turnover": safe_str(row.get("换手率", "")),
                "amount": safe_str(row.get("成交额", "")),
                "leading_stock": safe_str(row.get("领涨股票", row.get("领涨股", ""))),
                "leading_change": safe_str(row.get("领涨股票-涨跌幅", row.get("领涨股-涨跌幅", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_board_change_em",
            })
        return rows
    except Exception:
        return []


def fetch_limit_up_pool(max_rows: int) -> list[dict[str, str]]:
    """Fetch limit-up stock pool."""
    import akshare as ak

    try:
        frame = ak.stock_zt_pool_em()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "code": safe_str(row.get("代码", "")),
                "name": safe_str(row.get("名称", "")),
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "amount": safe_str(row.get("成交额", "")),
                "turnover": safe_str(row.get("换手率", "")),
                "market_cap": safe_str(row.get("流通市值", "")),
                "reason": safe_str(row.get("涨停统计", row.get("涨停原因", ""))),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_zt_pool_em",
            })
        return rows
    except Exception:
        return []


def fetch_stock_fund_flow_rank(max_rows: int) -> list[dict[str, str]]:
    """Fetch individual stock fund flow ranking."""
    import akshare as ak

    try:
        frame = ak.stock_individual_fund_flow_rank(indicator="今日")
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "code": safe_str(row.get("代码", "")),
                "name": safe_str(row.get("名称", "")),
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "main_net_inflow": safe_str(row.get("主力净流入-净额", "")),
                "main_net_pct": safe_str(row.get("主力净流入-净占比", "")),
                "super_large_net": safe_str(row.get("超大单净流入-净额", "")),
                "large_net": safe_str(row.get("大单净流入-净额", "")),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_individual_fund_flow_rank",
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
    for entry_file in ["market_context_fund_flow.csv", "market_context_board_changes.csv", "market_context_limit_up.csv", "market_context_stock_fund_flow.csv"]:
        has_entry = any(item.get("file") == entry_file for item in files)
        if not has_entry:
            files.append({
                "file": entry_file,
                "source_type": "public_market_data",
                "source_name": "AkShare 市场语境接口",
                "data_time": as_of,
                "period_or_basis": "当日快照",
                "verification_status": "verified",
                "missing_behavior": "市场语境字段写来源缺失，不作为基本面证据",
            })
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fund_flow = fetch_sector_fund_flow(args.max_rows)
    board_changes = fetch_board_changes(args.max_rows)
    limit_up = fetch_limit_up_pool(args.max_rows)
    stock_flow = fetch_stock_fund_flow_rank(args.max_rows)

    # Write fund flow
    fund_flow_cols = ["name", "change_pct", "main_net_inflow", "main_net_pct", "super_large_net", "large_net", "medium_net", "small_net", "source_type", "source_name"]
    write_csv(output_dir / "market_context_fund_flow.csv", fund_flow, fund_flow_cols)

    # Write board changes
    board_cols = ["board_name", "board_type", "change_pct", "turnover", "amount", "leading_stock", "leading_change", "source_type", "source_name"]
    write_csv(output_dir / "market_context_board_changes.csv", board_changes, board_cols)

    # Write limit-up pool
    limit_cols = ["code", "name", "change_pct", "amount", "turnover", "market_cap", "reason", "source_type", "source_name"]
    write_csv(output_dir / "market_context_limit_up.csv", limit_up, limit_cols)

    # Write stock fund flow rank
    stock_flow_cols = ["code", "name", "change_pct", "main_net_inflow", "main_net_pct", "super_large_net", "large_net", "source_type", "source_name"]
    write_csv(output_dir / "market_context_stock_fund_flow.csv", stock_flow, stock_flow_cols)

    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote market context: {len(fund_flow)} fund flow, {len(board_changes)} board changes, {len(limit_up)} limit-up, {len(stock_flow)} stock flow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
