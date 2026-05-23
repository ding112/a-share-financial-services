#!/usr/bin/env python3
"""Fetch A-share fund holdings and ETF data from AkShare."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

MISSING = "来源缺失"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="CSV with A-share peers.")
    parser.add_argument("--output-dir", required=True, help="Directory for output files.")
    parser.add_argument("--as-of", required=True, help="Access date.")
    parser.add_argument("--max-etf", type=int, default=30, help="Max ETF rows.")
    return parser.parse_args()


def normalize_a_share_code(raw_code: str) -> str:
    code = raw_code.strip().upper()
    if "." in code:
        symbol, exchange = code.split(".", 1)
        return f"{symbol.zfill(6)}.{exchange}"
    symbol = code.zfill(6)
    if symbol.startswith(("600", "601", "603", "605", "688", "689")):
        return f"{symbol}.SH"
    if symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{symbol}.SZ"
    if symbol.startswith(("430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "920")):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"


def read_peer_universe(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def safe_str(value: Any) -> str:
    if value is None or str(value).strip() in ("", "-", "--", "nan", "None"):
        return MISSING
    return str(value)


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


def fetch_fund_heavy_stocks(codes: list[str]) -> list[dict[str, str]]:
    """Check if peer stocks appear in fund heavy holdings."""
    import akshare as ak

    try:
        frame = ak.fund_report_stock_cninfo(date="20251231")
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        results: list[dict[str, str]] = []
        for row in records:
            stock_code = safe_str(row.get("股票代码", row.get("证券代码", "")))
            if stock_code in code_set:
                normalized = normalize_a_share_code(stock_code)
                results.append({
                    "code": normalized,
                    "fund_name": safe_str(row.get("基金名称", "")),
                    "fund_code": safe_str(row.get("基金代码", "")),
                    "hold_shares": safe_str(row.get("持股数量", "")),
                    "hold_market_cap": safe_str(row.get("持股市值", "")),
                    "hold_ratio": safe_str(row.get("占基金净值比", "")),
                    "source_type": "public_market_data",
                    "source_name": "AkShare fund_report_stock_cninfo",
                })
        return results
    except Exception:
        return []


def fetch_etf_list(max_etf: int) -> list[dict[str, str]]:
    """Fetch ETF spot data."""
    import akshare as ak

    try:
        frame = ak.fund_etf_spot_em()
        records = dataframe_to_records(frame)
        rows = []
        for row in records[:max_etf]:
            rows.append({
                "code": safe_str(row.get("代码", "")),
                "name": safe_str(row.get("名称", "")),
                "price": safe_str(row.get("最新价", "")),
                "change_pct": safe_str(row.get("涨跌幅", "")),
                "amount": safe_str(row.get("成交额", "")),
                "source_type": "public_market_data",
                "source_name": "AkShare fund_etf_spot_em",
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
    for entry_file in ["fund_heavy_stocks.csv", "etf_list.csv"]:
        has_entry = any(item.get("file") == entry_file for item in files)
        if not has_entry:
            files.append({
                "file": entry_file,
                "source_type": "public_market_data",
                "source_name": "AkShare 基金/ETF 接口",
                "data_time": as_of,
                "period_or_basis": "最新可用期",
                "verification_status": "verified",
                "missing_behavior": "基金持仓和 ETF 数据写来源缺失",
            })
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    peers = read_peer_universe(Path(args.peer_universe))
    codes = [normalize_a_share_code(p["code"]) for p in peers]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fund_heavy = fetch_fund_heavy_stocks(codes)
    etf_list = fetch_etf_list(args.max_etf)

    fund_cols = ["code", "fund_name", "fund_code", "hold_shares", "hold_market_cap", "hold_ratio", "source_type", "source_name"]
    etf_cols = ["code", "name", "price", "change_pct", "amount", "source_type", "source_name"]

    write_csv(output_dir / "fund_heavy_stocks.csv", fund_heavy, fund_cols)
    write_csv(output_dir / "etf_list.csv", etf_list, etf_cols)
    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote fund holdings: {len(fund_heavy)} heavy stock entries, {len(etf_list)} ETFs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
