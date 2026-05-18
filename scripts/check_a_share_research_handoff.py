#!/usr/bin/env python3
"""Validate the A-share research handoff generator."""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/generate_a_share_research_handoff.py"
COMPS_SCRIPT = ROOT / "scripts/generate_a_share_comps_artifacts.py"

FIXTURE_PACKS = [
    ("robotics-reducer", "机器人产业链"),
    ("cpo-optical-module", "CPO 光模块"),
    ("low-altitude-economy", "低空经济"),
]

REQUIRED_TOKENS = [
    "def parse_args",
    "def read_csv",
    "def write_csv",
    "def read_markdown_facts",
    "def build_competitive_handoff",
    "def build_idea_inputs",
    "def build_risk_register",
    "def write_summary",
    "def main",
    "--research-pack",
    "--comps-dir",
    "--output-dir",
    "--theme",
    "competitive_handoff.csv",
    "idea_inputs.csv",
    "idea_risk_register.csv",
    "research_handoff_summary.md",
]

REQUIRED_OUTPUTS = [
    "competitive_handoff.csv",
    "idea_inputs.csv",
    "idea_risk_register.csv",
    "research_handoff_summary.md",
]

REQUIRED_COMPETITIVE_COLUMNS = [
    "code",
    "name",
    "peer_group",
    "theme_role",
    "exposure_summary",
    "exposure_source_ref",
    "market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "revenue",
    "revenue_growth",
    "net_profit",
    "roe",
    "data_quality_flag",
    "risk_flags",
    "comps_handoff_note",
]

REQUIRED_IDEA_COLUMNS = [
    "code",
    "name",
    "research_priority",
    "theme_role",
    "theme_exposure",
    "valuation_or_quality_basis",
    "liquidity_basis",
    "why_now",
    "catalyst",
    "major_risks",
    "failure_conditions",
    "next_research_questions",
]

REQUIRED_RISK_COLUMNS = [
    "code",
    "name",
    "risk_type",
    "risk_detail",
    "source_ref",
    "idea_generation_action",
]

REQUIRED_SUMMARY_SECTIONS = [
    "## 竞争格局输入",
    "## comps 可用性",
    "## idea generation 入选池",
    "## 风险排除和降级",
    "## 下一步验证问题",
]


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)


def validate_research_handoff() -> list[str]:
    errors: list[str] = []
    if not SCRIPT.is_file():
        return [f"missing research handoff generator: {SCRIPT.relative_to(ROOT)}"]

    text = SCRIPT.read_text(encoding="utf-8")
    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"{SCRIPT.relative_to(ROOT)} missing token `{token}`")

    help_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if help_result.returncode != 0:
        errors.append(f"{SCRIPT.relative_to(ROOT)} --help exited {help_result.returncode}")
    for token in ["--research-pack", "--comps-dir", "--output-dir", "--theme"]:
        if token not in help_result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for pack_name, theme in FIXTURE_PACKS:
            pack_dir = ROOT / "fixtures/a-share-research-packs" / pack_name
            comps_dir = tmp_dir / f"{pack_name}-comps"
            handoff_dir = tmp_dir / f"{pack_name}-handoff"

            comps = subprocess.run(
                [
                    sys.executable,
                    str(COMPS_SCRIPT),
                    "--research-pack",
                    str(pack_dir),
                    "--output-dir",
                    str(comps_dir),
                    "--theme",
                    theme,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if comps.returncode != 0:
                errors.append(
                    f"comps generation for {pack_name} exited {comps.returncode}: "
                    f"{comps.stderr.strip()}"
                )
                continue

            handoff = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--research-pack",
                    str(pack_dir),
                    "--comps-dir",
                    str(comps_dir),
                    "--output-dir",
                    str(handoff_dir),
                    "--theme",
                    theme,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if handoff.returncode != 0:
                errors.append(
                    f"handoff generation for {pack_name} exited {handoff.returncode}: "
                    f"{handoff.stderr.strip()}"
                )
                continue

            for filename in REQUIRED_OUTPUTS:
                path = handoff_dir / filename
                if not path.is_file():
                    errors.append(f"{pack_name} handoff output missing {filename}")

            competitive_path = handoff_dir / "competitive_handoff.csv"
            if competitive_path.is_file():
                header = read_header(competitive_path)
                missing = [column for column in REQUIRED_COMPETITIVE_COLUMNS if column not in header]
                if missing:
                    errors.append(f"{pack_name} competitive_handoff.csv missing columns: {', '.join(missing)}")

            idea_path = handoff_dir / "idea_inputs.csv"
            if idea_path.is_file():
                header = read_header(idea_path)
                missing = [column for column in REQUIRED_IDEA_COLUMNS if column not in header]
                if missing:
                    errors.append(f"{pack_name} idea_inputs.csv missing columns: {', '.join(missing)}")

            risk_path = handoff_dir / "idea_risk_register.csv"
            if risk_path.is_file():
                header = read_header(risk_path)
                missing = [column for column in REQUIRED_RISK_COLUMNS if column not in header]
                if missing:
                    errors.append(f"{pack_name} idea_risk_register.csv missing columns: {', '.join(missing)}")

            summary_path = handoff_dir / "research_handoff_summary.md"
            if summary_path.is_file():
                summary = summary_path.read_text(encoding="utf-8")
                for section in REQUIRED_SUMMARY_SECTIONS:
                    if section not in summary:
                        errors.append(f"{pack_name} research_handoff_summary.md missing section {section}")

    return errors


def main() -> int:
    errors = validate_research_handoff()
    if errors:
        print(f"FAIL - {len(errors)} A-share research handoff issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share research handoff checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
