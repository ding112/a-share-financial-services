#!/usr/bin/env python3
"""Fetch A-share company details from AkShare."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

MISSING = "来源缺失"

PROFILE_FIELDS = [
    "company_name",
    "industry",
    "registered_capital",
    "established_date",
    "listing_date",
    "business_scope",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="CSV with A-share peers.")
    parser.add_argument("--output-dir", required=True, help="Directory for output files.")
    parser.add_argument("--as-of", required=True, help="Access date.")
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


def fetch_main_business(code: str) -> dict[str, str]:
    """Fetch main business composition."""
    import akshare as ak

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    try:
        frame = ak.stock_zygc_em(symbol=symbol)
        records = dataframe_to_records(frame)
        if not records:
            return {"main_business": MISSING, "main_business_source": "AkShare stock_zygc_em"}
        items = []
        for row in records[:10]:
            item_name = safe_str(row.get("项目名称", row.get("分产品", "")))
            revenue_pct = safe_str(row.get("主营业务收入占比", row.get("收入比例", "")))
            if item_name != MISSING:
                items.append(f"{item_name}({revenue_pct})")
        return {
            "main_business": "; ".join(items) if items else MISSING,
            "main_business_source": "AkShare stock_zygc_em",
        }
    except Exception:
        return {"main_business": MISSING, "main_business_source": "AkShare stock_zygc_em"}


def fetch_company_profile(code: str) -> dict[str, str]:
    """Fetch company profile from Cninfo via AkShare."""
    import akshare as ak

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    try:
        frame = ak.stock_profile_cninfo(symbol=symbol)
        records = dataframe_to_records(frame)
        if not records:
            return {field: MISSING for field in PROFILE_FIELDS} | {
                "profile_source": "AkShare stock_profile_cninfo"
            }
        row = records[0]
        return {
            "company_name": safe_str(row.get("公司名称", row.get("中文名称", ""))),
            "industry": safe_str(row.get("行业", row.get("所属行业", ""))),
            "registered_capital": safe_str(row.get("注册资本", "")),
            "established_date": safe_str(row.get("成立日期", "")),
            "listing_date": safe_str(row.get("上市日期", "")),
            "business_scope": safe_str(row.get("经营范围", ""))[:200] if safe_str(row.get("经营范围", "")) != MISSING else MISSING,
            "profile_source": "AkShare stock_profile_cninfo",
        }
    except Exception:
        return {field: MISSING for field in PROFILE_FIELDS} | {
            "profile_source": "AkShare stock_profile_cninfo"
        }


def fetch_share_structure(code: str) -> dict[str, str]:
    """Fetch share capital structure."""
    import akshare as ak

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    try:
        frame = ak.stock_zh_a_gbjg_em(symbol=symbol)
        records = dataframe_to_records(frame)
        if not records:
            return {"total_shares": MISSING, "float_shares": MISSING, "share_source": "AkShare stock_zh_a_gbjg_em"}
        row = records[0]
        return {
            "total_shares": safe_str(row.get("总股本", row.get("股份总数", ""))),
            "float_shares": safe_str(row.get("流通股", row.get("已流通股份", ""))),
            "share_source": "AkShare stock_zh_a_gbjg_em",
        }
    except Exception:
        return {"total_shares": MISSING, "float_shares": MISSING, "share_source": "AkShare stock_zh_a_gbjg_em"}


def write_company_details_csv(path: Path, rows: list[dict[str, str]]) -> None:
    cols = [
        "code", "name",
        "company_name", "industry", "registered_capital", "established_date", "listing_date",
        "business_scope", "main_business", "total_shares", "float_shares",
        "profile_source", "main_business_source", "share_source",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_source_manifest_entry(output_dir: Path, as_of: str) -> None:
    manifest_path = output_dir / "source_manifest.json"
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    has_entry = any(item.get("file") == "company_details.csv" for item in files)
    if not has_entry:
        files.append({
            "file": "company_details.csv",
            "source_type": "official_disclosure",
            "source_name": "AkShare 公司详情接口 (stock_zygc_em, stock_profile_cninfo, stock_zh_a_gbjg_em)",
            "data_time": as_of,
            "period_or_basis": "最新可用期",
            "verification_status": "verified",
            "missing_behavior": "公司详情字段写来源缺失",
        })
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    peers = read_peer_universe(Path(args.peer_universe))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for peer in peers:
        code = normalize_a_share_code(peer["code"])
        name = peer.get("name", code)

        profile = fetch_company_profile(code)
        main_biz = fetch_main_business(code)
        shares = fetch_share_structure(code)

        row = {"code": code, "name": name, **profile, **main_biz, **shares}
        rows.append(row)

    write_company_details_csv(output_dir / "company_details.csv", rows)
    write_source_manifest_entry(output_dir, args.as_of)

    print(f"wrote company_details.csv for {len(rows)} companies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
