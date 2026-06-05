#!/usr/bin/env python3
"""Validate the A-share annual report fetcher without network access."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/fetch_a_share_annual_reports.py"
FIXTURE_PACK = ROOT / "fixtures/a-share-research-packs/robotics-reducer"

REQUIRED_TOKENS = [
    "def parse_args",
    "def normalize_a_share_code",
    "def default_recent_annual_years",
    "def annual_report_filename",
    "def is_final_annual_report",
    "def cninfo_pdf_url",
    "def fetch_annual_report_index",
    "def download_annual_report_pdf",
    "def write_source_manifest_entries",
    "def write_fetch_errors",
    "def run_pipeline",
    "--peer-universe",
    "--output-dir",
    "--as-of",
    "--years",
    "--source",
    "annual_reports.csv",
    "annual_reports/",
]

REQUIRED_COLUMNS = [
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


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_a_share_annual_reports", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fetch_a_share_annual_reports module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_annual_report_fetcher() -> list[str]:
    errors: list[str] = []
    if not SCRIPT.is_file():
        return [f"missing annual report fetcher: {SCRIPT.relative_to(ROOT)}"]

    text = SCRIPT.read_text(encoding="utf-8")
    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"{SCRIPT.relative_to(ROOT)} missing token `{token}`")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        errors.append(f"{SCRIPT.relative_to(ROOT)} --help exited {result.returncode}")
    for token in ["--peer-universe", "--output-dir", "--as-of", "--years", "--source"]:
        if token not in result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    module = load_module()
    if module.default_recent_annual_years("2026-05-24") != [2025, 2024]:
        errors.append("default_recent_annual_years should return [2025, 2024] for 2026-05-24")
    if module.default_recent_annual_years("2026-01-15") != [2024, 2023]:
        errors.append("default_recent_annual_years should avoid assuming current-year annual reports")
    if not module.is_final_annual_report("2024年年度报告"):
        errors.append("is_final_annual_report should accept final annual reports")
    if module.is_final_annual_report("2024年年度报告摘要"):
        errors.append("is_final_annual_report should reject annual report summaries")
    if module.is_final_annual_report("2024年年度报告英文版"):
        errors.append("is_final_annual_report should reject English annual report variants")

    pdf_url = module.cninfo_pdf_url(
        "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300750&"
        "announcementId=1219550000&orgId=gfbj0835075&announcementTime=2025-04-25"
    )
    if pdf_url != "http://static.cninfo.com.cn/finalpage/2025-04-25/1219550000.PDF":
        errors.append(f"cninfo_pdf_url returned {pdf_url!r}")
    legacy_pdf_url = module.cninfo_pdf_url(
        "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300750&"
        "announcementId=1219550000&orgId=gfbj0835075"
    )
    if legacy_pdf_url != "http://static.cninfo.com.cn/finalpage/1219550000.PDF":
        errors.append(f"legacy cninfo_pdf_url returned {legacy_pdf_url!r}")

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "annual"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--peer-universe",
                str(FIXTURE_PACK / "peer_universe.csv"),
                "--output-dir",
                str(output_dir),
                "--as-of",
                "2026-05-24",
                "--source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"fixture smoke exited {result.returncode}: {result.stderr.strip()}")
        report_rows = read_rows(output_dir / "annual_reports.csv")
        if not report_rows:
            errors.append("fixture smoke should write annual_reports.csv rows")
        else:
            for column in REQUIRED_COLUMNS:
                if column not in report_rows[0]:
                    errors.append(f"annual_reports.csv missing column {column}")
            years = {row["report_year"] for row in report_rows}
            if years != {"2025", "2024"}:
                errors.append(f"fixture smoke should default to recent two annual years, got {years}")
            pdf_paths = [output_dir / row["local_pdf_path"] for row in report_rows]
            if not all(path.is_file() for path in pdf_paths):
                errors.append("fixture smoke should create local PDF files for every report row")

        manifest = json.loads((output_dir / "source_manifest.json").read_text(encoding="utf-8"))
        files = manifest.get("files", [])
        if not any(item.get("file") == "annual_reports.csv" for item in files):
            errors.append("source_manifest.json missing annual_reports.csv entry")
        if not any(item.get("file") == "annual_reports/" for item in files):
            errors.append("source_manifest.json missing annual_reports/ entry")

    original_modules = dict(sys.modules)
    try:
        class FakeFrame:
            def __init__(self, records: list[dict[str, object]]) -> None:
                self.records = records

            def to_dict(self, orient: str) -> list[dict[str, object]]:
                if orient != "records":
                    raise ValueError(f"unsupported orient: {orient}")
                return self.records

        def fake_report(
            symbol: str,
            market: str,
            keyword: str,
            category: str,
            start_date: str,
            end_date: str,
        ):
            if symbol != "300750":
                errors.append(f"cninfo query should use bare symbol, got {symbol}")
            if category != "年报":
                errors.append(f"cninfo query should use 年报 category, got {category}")
            if start_date != "20240101" or end_date != "20260430":
                errors.append(
                    "cninfo query should cover expected annual report disclosure window, "
                    f"got {start_date}~{end_date}"
                )
            return FakeFrame(
                [
                    {
                        "代码": "300750",
                        "简称": "宁德时代",
                        "公告标题": "宁德时代2025年年度报告摘要",
                        "公告时间": "2026-04-25 00:00:00",
                        "公告链接": (
                            "http://www.cninfo.com.cn/new/disclosure/detail?"
                            "stockCode=300750&announcementId=1219550001&orgId=x&"
                            "announcementTime=2026-04-25"
                        ),
                    },
                    {
                        "代码": "300750",
                        "简称": "宁德时代",
                        "公告标题": "宁德时代2025年年度报告",
                        "公告时间": "2026-04-25 00:00:00",
                        "公告链接": (
                            "http://www.cninfo.com.cn/new/disclosure/detail?"
                            "stockCode=300750&announcementId=1219550002&orgId=x&"
                            "announcementTime=2026-04-25"
                        ),
                    },
                ]
            )

        import types

        sys.modules["akshare"] = types.SimpleNamespace(
            stock_zh_a_disclosure_report_cninfo=fake_report
        )
        cninfo_rows = module.fetch_cninfo_annual_report_index(
            {"code": "300750.SZ", "name": "宁德时代"},
            [2025, 2024],
        )
        if len(cninfo_rows) != 1:
            errors.append(f"cninfo adapter should keep only final annual reports, got {len(cninfo_rows)}")
        elif cninfo_rows[0]["report_year"] != "2025":
            errors.append("cninfo adapter should infer report year from annual report title")
    finally:
        sys.modules.clear()
        sys.modules.update(original_modules)

    return errors


def main() -> int:
    errors = validate_annual_report_fetcher()
    if errors:
        print(f"FAIL - {len(errors)} A-share annual report fetcher issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share annual report fetcher checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
