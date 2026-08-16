#!/usr/bin/env python3
"""Validate the A-share research-pack prep script."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare_a_share_research_pack.py"
FINANCIAL_STATEMENTS_COLUMNS = [
    "statement_item_id", "security_code", "security_name", "organization_type",
    "statement_type", "period", "report_type", "notice_date", "update_date",
    "currency", "statement_scope", "source_line_item", "normalized_line_item",
    "value", "unit", "value_semantics", "domestic_audit_opinion",
    "overseas_audit_opinion", "source_type", "source_name", "verification_status", "basis",
]

REQUIRED_TOKENS = [
    "def parse_args",
    "def load_source_manifest",
    "def write_source_manifest",
    "def copy_required_inputs",
    "def main",
    "--input-dir",
    "--output-dir",
    "--theme",
    "--as-of",
    "source_manifest.json",
    "peer_universe.csv",
    "market_snapshot.csv",
    "financial_summary.csv",
    "company_exposure.md",
    "events_and_risks.md",
    '"market_snapshot.csv": "market_snapshot.csv"',
    '"financial_summary.csv": "financial_summary.csv"',
    '"financial_statements.csv": "financial_statements.csv"',
    "FINANCIAL_STATEMENTS_COLUMNS",
]


def validate_prep_script() -> list[str]:
    errors: list[str] = []
    if not SCRIPT.is_file():
        return [f"missing prep script: {SCRIPT.relative_to(ROOT)}"]

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
    for token in ["--input-dir", "--output-dir", "--theme", "--as-of"]:
        if token not in result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        input_dir = Path(tmp) / "input"
        output_dir = Path(tmp) / "测试主题" / "research-pack"
        input_dir.mkdir()
        (input_dir / "peer_universe.csv").write_text(
            "code,name,exchange,board,peer_group,theme_role,exposure_summary,exposure_source_ref\n"
            "300750.SZ,宁德时代,SZ,创业板,电池,中游,动力电池,company_exposure.md#300750\n",
            encoding="utf-8",
        )
        (input_dir / "market_snapshot.csv").write_text("code,basis\n300750.SZ,canonical\n", encoding="utf-8")
        (input_dir / "tencent_quotes.csv").write_text("code,basis\n300750.SZ,legacy\n", encoding="utf-8")
        (input_dir / "financial_summary.csv").write_text("code,basis\n300750.SZ,canonical\n", encoding="utf-8")
        (input_dir / "akshare_financial_summary.csv").write_text("code,basis\n300750.SZ,legacy\n", encoding="utf-8")
        financial_header = ",".join(FINANCIAL_STATEMENTS_COLUMNS)
        financial_content = financial_header + "\nitem-1,300750.SZ,宁德时代,一般企业,balance_sheet,2025-12-31,年报,2026-03-01,2026-03-02,CNY,来源缺失,MONETARYFUNDS,monetary_funds,1,元,point_in_time,来源缺失,来源缺失,public_market_data,AkShare,verified,fixture\n"
        (input_dir / "financial_statements.csv").write_text(financial_content, encoding="utf-8")
        smoke = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
                "--theme",
                "测试主题",
                "--as-of",
                "2026-05-21",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if smoke.returncode != 0:
            errors.append(f"{SCRIPT.relative_to(ROOT)} smoke exited {smoke.returncode}: {smoke.stderr.strip()}")
        market_output = output_dir / "market_snapshot.csv"
        financial_output = output_dir / "financial_summary.csv"
        if not market_output.is_file():
            errors.append("prepare script smoke output missing market_snapshot.csv")
        elif market_output.read_text(encoding="utf-8").find("canonical") == -1:
            errors.append("prepare script did not prefer canonical market_snapshot.csv")
        if not financial_output.is_file():
            errors.append("prepare script smoke output missing financial_summary.csv")
        elif financial_output.read_text(encoding="utf-8").find("canonical") == -1:
            errors.append("prepare script did not prefer canonical financial_summary.csv")
        statements_output = output_dir / "financial_statements.csv"
        if not statements_output.is_file() or statements_output.read_text(encoding="utf-8") != financial_content:
            errors.append("prepare script did not copy standard financial_statements.csv byte-for-byte")

        bad_input = Path(tmp) / "bad-input"
        bad_output = Path(tmp) / "bad-output"
        bad_input.mkdir()
        (bad_input / "peer_universe.csv").write_text(
            (input_dir / "peer_universe.csv").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (bad_input / "financial_statements.csv").write_text("wide,table\n1,2\n", encoding="utf-8")
        rejected = subprocess.run(
            [
                sys.executable, str(SCRIPT), "--input-dir", str(bad_input),
                "--output-dir", str(bad_output), "--theme", "测试主题", "--as-of", "2026-05-21",
            ], cwd=ROOT, check=False, capture_output=True, text=True,
        )
        if rejected.returncode == 0 or "financial_statements.csv" not in rejected.stderr:
            errors.append("prepare script should reject non-standard financial_statements.csv headers")

    return errors


def main() -> int:
    errors = validate_prep_script()
    if errors:
        print(f"FAIL - {len(errors)} A-share prep script issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share research-pack prep script checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
