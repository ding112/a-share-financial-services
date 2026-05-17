#!/usr/bin/env python3
"""Validate the A-share comps artifact contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md"
BUNDLED = ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md"

REQUIRED_SECTIONS = [
    "## Comps artifact contract",
    "### `comps_main.csv`",
    "### `comps_source_notes.csv`",
    "### `comps_exceptions.csv`",
    "### `comps_statistics.csv`",
    "### `comps_data_gaps.csv`",
    "### `comps_summary.md`",
]

REQUIRED_ARTIFACT_FILES = [
    "comps_main.csv",
    "comps_source_notes.csv",
    "comps_exceptions.csv",
    "comps_statistics.csv",
    "comps_data_gaps.csv",
    "comps_summary.md",
]

REQUIRED_FIELDS = [
    "code",
    "name",
    "peer_group",
    "theme_role",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "revenue",
    "net_profit",
    "roe",
    "source_type",
    "source_name",
    "data_time",
    "period_or_basis",
    "verification_status",
    "missing_behavior",
    "exception_type",
    "metric",
    "median",
    "average",
    "minimum",
    "maximum",
    "quartile_1",
    "quartile_3",
]


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_contract() -> list[str]:
    errors: list[str] = []
    text = _read(SOURCE)

    for heading in REQUIRED_SECTIONS:
        if heading not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing section {heading}")

    for filename in REQUIRED_ARTIFACT_FILES:
        if filename not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing artifact file `{filename}`")

    for field in REQUIRED_FIELDS:
        if field not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing artifact field `{field}`")

    if SOURCE.is_file() and BUNDLED.is_file() and _read(SOURCE) != _read(BUNDLED):
        errors.append(
            "a-share-comps-analysis bundled copy drifted from vertical source "
            "(run scripts/sync-agent-skills.py)"
        )

    return errors


def main() -> int:
    errors = validate_contract()
    if errors:
        print(f"FAIL - {len(errors)} A-share comps artifact issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share comps artifact contract checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
