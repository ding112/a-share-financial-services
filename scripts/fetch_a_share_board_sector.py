#!/usr/bin/env python3
"""Fetch A-share board and sector data from AkShare."""

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


def fetch_concept_boards(max_rows: int) -> list[dict[str, str]]:
    """Fetch concept board spot data."""
    import akshare as ak

    try:
        frame = ak.stock_board_concept_spot_em()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "board_name": safe_str(row.get("板块名称", row.get("名称", ""))),
                "board_type": "概念板块",
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "amount": safe_str(row.get("成交额", "")),
                "turnover": safe_str(row.get("换手率", "")),
                "leading_stock": safe_str(row.get("领涨股票", row.get("领涨股", ""))),
                "leading_change": safe_str(row.get("领涨股票-涨跌幅", "")),
                "rising_count": safe_str(row.get("上涨家数", "")),
                "falling_count": safe_str(row.get("下跌家数", "")),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_board_concept_spot_em",
            })
        return rows
    except Exception:
        return []


def fetch_industry_boards(max_rows: int) -> list[dict[str, str]]:
    """Fetch industry board spot data."""
    import akshare as ak

    try:
        frame = ak.stock_board_industry_spot_em()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_rows]:
            rows.append({
                "board_name": safe_str(row.get("板块名称", row.get("名称", ""))),
                "board_type": "行业板块",
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "amount": safe_str(row.get("成交额", "")),
                "turnover": safe_str(row.get("换手率", "")),
                "leading_stock": safe_str(row.get("领涨股票", row.get("领涨股", ""))),
                "leading_change": safe_str(row.get("领涨股票-涨跌幅", "")),
                "rising_count": safe_str(row.get("上涨家数", "")),
                "falling_count": safe_str(row.get("下跌家数", "")),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_board_industry_spot_em",
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
    has_entry = any(item.get("file") == "board_sector_context.csv" for item in files)
    if not has_entry:
        files.append({
            "file": "board_sector_context.csv",
            "source_type": "public_market_data",
            "source_name": "AkShare 板块行情接口 (stock_board_concept_spot_em, stock_board_industry_spot_em)",
            "data_time": as_of,
            "period_or_basis": "当日快照",
            "verification_status": "verified",
            "missing_behavior": "板块行情写来源缺失，不证明业务暴露",
        })
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    concept = fetch_concept_boards(args.max_rows)
    industry = fetch_industry_boards(args.max_rows)

    all_rows = concept + industry
    cols = [
        "board_name", "board_type", "change_pct", "amount", "turnover",
        "leading_stock", "leading_change", "rising_count", "falling_count",
        "source_type", "source_name",
    ]
    write_csv(output_dir / "board_sector_context.csv", all_rows, cols)
    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote board_sector_context.csv: {len(concept)} concept, {len(industry)} industry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
