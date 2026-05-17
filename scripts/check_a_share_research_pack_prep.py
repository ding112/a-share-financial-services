#!/usr/bin/env python3
"""Validate the A-share research-pack prep script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare_a_share_research_pack.py"

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
