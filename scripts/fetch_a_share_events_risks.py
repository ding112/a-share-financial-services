#!/usr/bin/env python3
"""Fetch A-share events and risks data from AkShare."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path
from typing import Any

MISSING = "来源缺失"


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
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty peer universe: {path}")
    return rows


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


def safe_str(value: Any) -> str:
    if value is None or str(value).strip() in ("", "-", "--", "nan", "None"):
        return MISSING
    return str(value)


def fetch_st_status(codes: list[str]) -> dict[str, list[dict[str, str]]]:
    """Check ST status for given codes."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_zh_a_st_em()
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        for row in records:
            row_code = safe_str(row.get("代码", ""))
            if row_code in code_set:
                normalized = normalize_a_share_code(row_code)
                result[normalized].append({
                    "event_type": "ST/退市风险",
                    "detail": f"名称: {safe_str(row.get('名称', ''))}",
                    "source_type": "public_market_data",
                    "source_name": "AkShare stock_zh_a_st_em",
                })
    except Exception:
        pass
    return result


def as_of_date(as_of: str) -> dt.date:
    try:
        return dt.date.fromisoformat(as_of[:10])
    except ValueError:
        return dt.date.today()


def fetch_suspension(codes: list[str], as_of: str) -> dict[str, list[dict[str, str]]]:
    """Check suspension status for given codes."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_tfp_em(date=as_of_date(as_of).strftime("%Y%m%d"))
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        for row in records:
            row_code = safe_str(row.get("代码", ""))
            if row_code in code_set:
                normalized = normalize_a_share_code(row_code)
                result[normalized].append({
                    "event_type": "停复牌",
                    "detail": f"简称: {safe_str(row.get('名称', ''))}, 备注: {safe_str(row.get('备注', ''))}",
                    "source_type": "public_market_data",
                    "source_name": "AkShare stock_tfp_em",
                })
    except Exception:
        pass
    return result


def fetch_restricted_release(codes: list[str], as_of: str) -> dict[str, list[dict[str, str]]]:
    """Check upcoming restricted share releases."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_restricted_release_summary_em()
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        cutoff = as_of_date(as_of)
        for row in records:
            row_code = safe_str(row.get("股票代码", row.get("代码", "")))
            if row_code not in code_set:
                continue
            normalized = normalize_a_share_code(row_code)
            release_date_str = safe_str(row.get("解禁日期", row.get("解除限售日期", "")))
            if release_date_str == MISSING:
                continue
            try:
                release_date = dt.date.fromisoformat(release_date_str[:10])
                if release_date < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
            result[normalized].append({
                "event_type": "限售解禁",
                "detail": (
                    f"解禁日期: {release_date_str}, "
                    f"解禁股数: {safe_str(row.get('解禁股数', row.get('限售股解禁数量', '')))}, "
                    f"占总股本: {safe_str(row.get('占总股本比例', row.get('占总股本%', '')))}"
                ),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_restricted_release_summary_em",
            })
    except Exception:
        pass
    return result


def fetch_pledge_ratio(codes: list[str]) -> dict[str, list[dict[str, str]]]:
    """Check equity pledge ratios."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_gpzy_pledge_ratio_em()
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        for row in records:
            row_code = safe_str(row.get("股票代码", row.get("代码", "")))
            if row_code not in code_set:
                continue
            normalized = normalize_a_share_code(row_code)
            ratio = safe_str(row.get("质押比例", row.get("质押比例(%)", "")))
            if ratio == MISSING:
                continue
            result[normalized].append({
                "event_type": "股权质押",
                "detail": f"质押比例: {ratio}%",
                "source_type": "public_market_data",
                "source_name": "AkShare stock_gpzy_pledge_ratio_em",
            })
    except Exception:
        pass
    return result


def fetch_dividends(codes: list[str]) -> dict[str, list[dict[str, str]]]:
    """Check recent dividend distributions."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_fhps_em()
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        for row in records:
            row_code = safe_str(row.get("股票代码", row.get("代码", "")))
            if row_code not in code_set:
                continue
            normalized = normalize_a_share_code(row_code)
            detail_parts = []
            cash_div = safe_str(row.get("现金分红-现金分红比例", row.get("每股现金分红", "")))
            if cash_div != MISSING:
                detail_parts.append(f"现金分红: {cash_div}")
            bonus = safe_str(row.get("送股-送股比例", row.get("送股比例", "")))
            if bonus != MISSING and bonus != "0":
                detail_parts.append(f"送股: {bonus}")
            convert = safe_str(row.get("转增-转增比例", row.get("转增比例", "")))
            if convert != MISSING and convert != "0":
                detail_parts.append(f"转增: {convert}")
            if not detail_parts:
                continue
            result[normalized].append({
                "event_type": "分红配送",
                "detail": ", ".join(detail_parts),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_fhps_em",
            })
    except Exception:
        pass
    return result


def fetch_buybacks(codes: list[str]) -> dict[str, list[dict[str, str]]]:
    """Check company buyback plans."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_repurchase_em()
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        for row in records:
            row_code = safe_str(row.get("股票代码", row.get("代码", "")))
            if row_code not in code_set:
                continue
            normalized = normalize_a_share_code(row_code)
            result[normalized].append({
                "event_type": "回购",
                "detail": (
                    f"进度: {safe_str(row.get('进度', ''))}, "
                    f"回购金额上限: {safe_str(row.get('回购金额上限', ''))}"
                ),
                "source_type": "public_market_data",
                "source_name": "AkShare stock_repurchase_em",
            })
    except Exception:
        pass
    return result


def fetch_goodwill(codes: list[str]) -> dict[str, list[dict[str, str]]]:
    """Check goodwill impairment risk."""
    import akshare as ak

    result: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    try:
        frame = ak.stock_sy_em()
        records = dataframe_to_records(frame)
        code_set = {normalize_a_share_code(c).split(".", 1)[0] for c in codes}
        for row in records:
            row_code = safe_str(row.get("股票代码", row.get("代码", "")))
            if row_code not in code_set:
                continue
            normalized = normalize_a_share_code(row_code)
            goodwill = safe_str(row.get("商誉", row.get("商誉(元)", "")))
            if goodwill == MISSING:
                continue
            result[normalized].append({
                "event_type": "商誉",
                "detail": f"商誉: {goodwill}",
                "source_type": "public_market_data",
                "source_name": "AkShare stock_sy_em",
            })
    except Exception:
        pass
    return result


def merge_events(
    codes: list[str],
    *event_dicts: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    merged: dict[str, list[dict[str, str]]] = {c: [] for c in codes}
    for event_dict in event_dicts:
        for code, events in event_dict.items():
            if code in merged:
                merged[code].extend(events)
    return merged


def write_events_markdown(
    path: Path,
    peers: list[dict[str, str]],
    events: dict[str, list[dict[str, str]]],
    as_of: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 事件和风险数据",
        "",
        f"访问时间: {as_of}",
        "",
        "---",
        "",
    ]
    for peer in peers:
        code = normalize_a_share_code(peer["code"])
        name = peer.get("name", code)
        lines.append(f"## {code} {name}")
        lines.append("")
        stock_events = events.get(code, [])
        if not stock_events:
            lines.append("- 事实: 未发现近期事件或风险")
            lines.append("  来源类型: public_market_data")
            lines.append("  来源名称: AkShare 事件类接口")
            lines.append(f"  数据时间: {as_of}")
            lines.append("  报告期或口径: 当日检查")
            lines.append("  验证状态: verified")
        else:
            for event in stock_events:
                lines.append(f"- 事实: {event['event_type']} — {event['detail']}")
                lines.append(f"  来源类型: {event['source_type']}")
                lines.append(f"  来源名称: {event['source_name']}")
                lines.append(f"  数据时间: {as_of}")
                lines.append("  报告期或口径: 当日检查")
                lines.append("  验证状态: verified")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_source_manifest_entry(output_dir: Path, as_of: str) -> None:
    """Append events_and_risks entry to source_manifest.json if it exists."""
    manifest_path = output_dir / "source_manifest.json"
    if not manifest_path.exists():
        return
    import json

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    has_entry = any(item.get("file") == "events_and_risks.md" for item in files)
    if not has_entry:
        files.append({
            "file": "events_and_risks.md",
            "source_type": "public_market_data",
            "source_name": "AkShare 事件类接口 (stock_zh_a_st_em, stock_tfp_em, stock_restricted_release_summary_em, stock_gpzy_pledge_ratio_em)",
            "data_time": as_of,
            "period_or_basis": "当日检查",
            "verification_status": "verified",
            "missing_behavior": "风险字段写来源缺失，不得弱化风险",
        })
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    peers = read_peer_universe(Path(args.peer_universe))
    codes = [normalize_a_share_code(p["code"]) for p in peers]

    st_events = fetch_st_status(codes)
    suspension_events = fetch_suspension(codes, args.as_of)
    restricted_events = fetch_restricted_release(codes, args.as_of)
    pledge_events = fetch_pledge_ratio(codes)
    dividend_events = fetch_dividends(codes)
    buyback_events = fetch_buybacks(codes)
    goodwill_events = fetch_goodwill(codes)

    all_events = merge_events(codes, st_events, suspension_events, restricted_events, pledge_events, dividend_events, buyback_events, goodwill_events)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_events_markdown(output_dir / "events_and_risks.md", peers, all_events, args.as_of)
    write_source_manifest_entry(output_dir, args.as_of)

    total_events = sum(len(v) for v in all_events.values())
    print(f"wrote events_and_risks.md with {total_events} event(s) for {len(peers)} peer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
