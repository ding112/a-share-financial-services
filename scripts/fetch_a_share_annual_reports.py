#!/usr/bin/env python3
"""Fetch recent A-share annual reports for research-pack preparation."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MISSING = "来源缺失"
USER_AGENT = "Mozilla/5.0 a-share-market-researcher/0.1"

REPORT_COLUMNS = [
    "code",
    "name",
    "report_year",
    "announcement_title",
    "announcement_date",
    "disclosure_url",
    "pdf_url",
    "local_pdf_path",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]

ERROR_COLUMNS = ["code", "source", "stage", "error"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="CSV with A-share peers.")
    parser.add_argument("--output-dir", required=True, help="Directory for annual report files.")
    parser.add_argument("--as-of", required=True, help="Access date, for example 2026-05-24.")
    parser.add_argument(
        "--years",
        help="Comma-separated annual report years. Defaults to recent two available annual years.",
    )
    parser.add_argument(
        "--source",
        choices=["cninfo", "fixture"],
        default="cninfo",
        help="Annual report source.",
    )
    return parser.parse_args()


def normalize_a_share_code(raw_code: str) -> str:
    code = raw_code.strip().upper()
    if "." in code:
        symbol, exchange = code.split(".", 1)
        return f"{symbol.zfill(6)}.{exchange}"
    symbol = code.zfill(6)
    if symbol.startswith(("600", "601", "603", "605", "688", "689")):
        return f"{symbol}.SH"
    if symbol.startswith(
        (
            "430",
            "830",
            "831",
            "832",
            "833",
            "834",
            "835",
            "836",
            "837",
            "838",
            "839",
            "870",
            "871",
            "872",
            "873",
            "920",
        )
    ):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"


def default_recent_annual_years(as_of: str) -> list[int]:
    date = dt.date.fromisoformat(as_of[:10])
    latest = date.year - 1
    if date.month < 5:
        latest = date.year - 2
    return [latest, latest - 1]


def parse_years(years: str | None, as_of: str) -> list[int]:
    if not years:
        return default_recent_annual_years(as_of)
    parsed = [int(item.strip()) for item in years.split(",") if item.strip()]
    if not parsed:
        raise ValueError("--years must contain at least one year")
    return parsed


def read_peer_universe(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty peer universe: {path}")
    if any("code" not in row or not row["code"].strip() for row in rows):
        raise ValueError(f"peer universe requires non-empty code column: {path}")
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_final_annual_report(title: str) -> bool:
    title = title.strip()
    if "年度报告" not in title and "年年度报告" not in title:
        return False
    excluded = ["摘要", "英文", "取消", "更正", "修订", "已取消", "提示性公告"]
    return not any(marker in title for marker in excluded)


def cninfo_pdf_url(disclosure_url: str) -> str:
    parsed = urllib.parse.urlparse(disclosure_url)
    query = urllib.parse.parse_qs(parsed.query)
    announcement_id = query.get("announcementId", [""])[0]
    if not announcement_id:
        raise ValueError(f"cannot parse announcementId from {disclosure_url}")
    announcement_time = query.get("announcementTime", [""])[0][:10]
    if re.fullmatch(r"[12][0-9]{3}-[01][0-9]-[0-3][0-9]", announcement_time):
        return f"http://static.cninfo.com.cn/finalpage/{announcement_time}/{announcement_id}.PDF"
    return f"http://static.cninfo.com.cn/finalpage/{announcement_id}.PDF"


def annual_report_filename(code: str, report_year: int, title: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", title).strip("-")
    return f"{code}-{report_year}-{cleaned}.pdf"


def fixture_index_row(peer: dict[str, str], report_year: int) -> dict[str, str]:
    code = normalize_a_share_code(peer["code"])
    name = peer.get("name") or code
    symbol = code.split(".", 1)[0]
    announcement_id = f"{report_year}{symbol[-4:]}"
    announcement_date = f"{report_year + 1}-04-25"
    disclosure_url = (
        "http://www.cninfo.com.cn/new/disclosure/detail?"
        f"stockCode={symbol}&announcementId={announcement_id}&orgId=fixture&"
        f"announcementTime={announcement_date}"
    )
    return {
        "code": code,
        "name": name,
        "report_year": str(report_year),
        "announcement_title": f"{name}{report_year}年年度报告",
        "announcement_date": announcement_date,
        "disclosure_url": disclosure_url,
        "pdf_url": cninfo_pdf_url(disclosure_url),
    }


def disclosure_window(years: list[int]) -> tuple[str, str]:
    start_year = min(years)
    end_year = max(years) + 1
    return f"{start_year}0101", f"{end_year}0430"


def report_year_from_title(title: str) -> int | None:
    match = re.search(r"([12][0-9]{3})年年度报告", title)
    if not match:
        return None
    return int(match.group(1))


def fetch_annual_report_index(
    peer: dict[str, str],
    years: list[int],
    source: str,
) -> list[dict[str, str]]:
    if source == "fixture":
        return [fixture_index_row(peer, year) for year in years]
    return fetch_cninfo_annual_report_index(peer, years)


def fetch_cninfo_annual_report_index(
    peer: dict[str, str],
    years: list[int],
) -> list[dict[str, str]]:
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:
        raise RuntimeError("cninfo source requires AkShare installed in the current environment") from exc

    code = normalize_a_share_code(peer["code"])
    symbol = code.split(".", 1)[0]
    start_date, end_date = disclosure_window(years)
    frame = ak.stock_zh_a_disclosure_report_cninfo(
        symbol=symbol,
        market="沪深京",
        keyword="",
        category="年报",
        start_date=start_date,
        end_date=end_date,
    )
    records = [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]
    wanted = set(years)
    rows: list[dict[str, str]] = []
    seen_years: set[int] = set()
    for record in records:
        title = str(record.get("公告标题", ""))
        year = report_year_from_title(title)
        if year not in wanted or year in seen_years:
            continue
        if not is_final_annual_report(title):
            continue
        disclosure_url = str(record.get("公告链接", ""))
        rows.append(
            {
                "code": code,
                "name": str(record.get("简称") or peer.get("name") or code),
                "report_year": str(year),
                "announcement_title": title,
                "announcement_date": str(record.get("公告时间", ""))[:10],
                "disclosure_url": disclosure_url,
                "pdf_url": cninfo_pdf_url(disclosure_url),
            }
        )
        seen_years.add(year)
    missing_years = wanted - seen_years
    if missing_years and not rows:
        raise RuntimeError(f"missing final annual reports for years: {sorted(missing_years)}")
    return rows


def download_annual_report_pdf(row: dict[str, str], output_dir: Path, source: str) -> str:
    reports_dir = output_dir / "annual_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = annual_report_filename(row["code"], int(row["report_year"]), row["announcement_title"])
    target = reports_dir / filename
    if source == "fixture":
        target.write_bytes(b"%PDF-1.4\n% fixture annual report\n%%EOF\n")
    else:
        request = urllib.request.Request(row["pdf_url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            target.write_bytes(response.read())
    return str(target.relative_to(output_dir))


def append_manifest_entry(files: list[dict[str, str]], entry: dict[str, str]) -> None:
    key = (entry["file"], entry.get("field_group", ""))
    files[:] = [item for item in files if (item.get("file"), item.get("field_group", "")) != key]
    files.append(entry)


def write_source_manifest_entries(output_dir: Path, as_of: str, years: list[int]) -> None:
    path = output_dir / "source_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"files": []}
    files = data.setdefault("files", [])
    basis = f"最近2个年报年度: {','.join(str(year) for year in years)}"
    append_manifest_entry(
        files,
        {
            "file": "annual_reports.csv",
            "source_type": "official_disclosure",
            "source_name": "巨潮资讯定期报告公告",
            "data_time": as_of,
            "period_or_basis": basis,
            "verification_status": "verified",
            "missing_behavior": "缺失时公司业务暴露、订单、产能、客户和技术路线保持待验证",
        },
    )
    append_manifest_entry(
        files,
        {
            "file": "annual_reports/",
            "source_type": "official_disclosure",
            "source_name": "巨潮资讯年报 PDF",
            "data_time": as_of,
            "period_or_basis": basis,
            "verification_status": "verified",
            "missing_behavior": "缺失时不得从年报原文抽取 official_disclosure 证据",
        },
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_fetch_errors(output_dir: Path, errors: list[dict[str, str]]) -> None:
    path = output_dir / "fetch_errors.csv"
    existing: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = list(csv.DictReader(handle))
    write_csv(path, existing + errors, ERROR_COLUMNS)


def run_pipeline(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    years = parse_years(args.years, args.as_of)
    peers = read_peer_universe(Path(args.peer_universe))
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for peer in peers:
        code = normalize_a_share_code(peer["code"])
        try:
            index_rows = fetch_annual_report_index(peer, years, args.source)
            for row in index_rows:
                local_pdf_path = download_annual_report_pdf(row, output_dir, args.source)
                rows.append(
                    {
                        **row,
                        "local_pdf_path": local_pdf_path,
                        "source_type": "official_disclosure",
                        "source_name": "巨潮资讯",
                        "verification_status": "verified",
                        "basis": "年度报告原文 PDF",
                    }
                )
        except Exception as exc:
            errors.append(
                {
                    "code": code,
                    "source": args.source,
                    "stage": "annual_report",
                    "error": str(exc),
                }
            )
    write_csv(output_dir / "annual_reports.csv", rows, REPORT_COLUMNS)
    write_source_manifest_entries(output_dir, args.as_of, years)
    write_fetch_errors(output_dir, errors)


def main() -> int:
    args = parse_args()
    run_pipeline(args)
    print(f"wrote annual reports: {Path(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
