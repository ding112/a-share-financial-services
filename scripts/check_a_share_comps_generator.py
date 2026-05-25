#!/usr/bin/env python3
"""Validate the A-share comps artifact generator."""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/generate_a_share_comps_artifacts.py"
FIXTURE_PACKS = [
    ("robotics-reducer", "机器人产业链"),
    ("cpo-optical-module", "CPO 光模块"),
    ("low-altitude-economy", "低空经济"),
]

REQUIRED_TOKENS = [
    "def parse_args",
    "def read_csv",
    "def write_csv",
    "def read_source_manifest",
    "def build_comps_main",
    "def build_source_notes",
    "def build_exceptions",
    "def build_statistics",
    "def build_data_gaps",
    "def write_summary",
    "def main",
    "--research-pack",
    "--output-dir",
    "--theme",
    "comps_main.csv",
    "comps_source_notes.csv",
    "comps_exceptions.csv",
    "comps_statistics.csv",
    "comps_data_gaps.csv",
    "comps_summary.md",
]

REQUIRED_OUTPUTS = [
    "comps_main.csv",
    "comps_source_notes.csv",
    "comps_exceptions.csv",
    "comps_statistics.csv",
    "comps_data_gaps.csv",
    "comps_summary.md",
]

REQUIRED_MAIN_COLUMNS = [
    "code",
    "name",
    "peer_group",
    "theme_role",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "return_5d",
    "return_20d",
    "revenue",
    "net_profit",
    "roe",
    "liquidity_basis",
    "financial_period",
    "data_quality_flag",
]

REQUIRED_STAT_COLUMNS = [
    "metric",
    "sample_size",
    "median",
    "average",
    "minimum",
    "maximum",
    "quartile_1",
    "quartile_3",
    "included_codes",
    "excluded_codes",
]

REQUIRED_SUMMARY_SECTIONS = [
    "## 可用数据",
    "## 不可用于排序的数据",
    "## 异常值和不可比项",
    "## 统计分布",
    "## 对 idea generation 的交接",
]


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)


def validate_comps_generator() -> list[str]:
    errors: list[str] = []
    if not SCRIPT.is_file():
        return [f"missing comps generator: {SCRIPT.relative_to(ROOT)}"]

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
    for token in ["--research-pack", "--output-dir", "--theme"]:
        if token not in result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        for pack_name, theme in FIXTURE_PACKS:
            fixture_pack = ROOT / "fixtures/a-share-research-packs" / pack_name
            topic_dir = Path(tmp) / theme
            output_dir = topic_dir / "comps"
            default_smoke = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--research-pack",
                    str(fixture_pack),
                    "--theme",
                    theme,
                ],
                cwd=tmp,
                check=False,
                capture_output=True,
                text=True,
            )
            if default_smoke.returncode != 0:
                errors.append(
                    f"{SCRIPT.relative_to(ROOT)} default output smoke for {pack_name} "
                    f"exited {default_smoke.returncode}: {default_smoke.stderr.strip()}"
                )
                continue
            default_output_dir = Path(tmp) / "out" / theme / "comps"
            if not (default_output_dir / "comps_summary.md").is_file():
                errors.append(f"{pack_name} default comps output should be out/<theme>/comps")

            smoke = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--research-pack",
                    str(fixture_pack),
                    "--output-dir",
                    str(output_dir),
                    "--theme",
                    theme,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if smoke.returncode != 0:
                errors.append(
                    f"{SCRIPT.relative_to(ROOT)} smoke test for {pack_name} "
                    f"exited {smoke.returncode}: {smoke.stderr.strip()}"
                )
                continue

            for filename in REQUIRED_OUTPUTS:
                path = output_dir / filename
                if not path.is_file():
                    errors.append(f"{pack_name} smoke output missing {filename}")

            main_path = output_dir / "comps_main.csv"
            if main_path.is_file():
                header = read_header(main_path)
                missing = [column for column in REQUIRED_MAIN_COLUMNS if column not in header]
                if missing:
                    errors.append(f"{pack_name} comps_main.csv missing columns: {', '.join(missing)}")
                with main_path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                if rows and pack_name != "low-altitude-economy":
                    first = rows[0]
                    if first.get("return_5d") in {"", "来源缺失", None}:
                        errors.append(f"{pack_name} comps_main.csv should expose return_5d")
                    if first.get("return_20d") in {"", "来源缺失", None}:
                        errors.append(f"{pack_name} comps_main.csv should expose return_20d")

            stat_path = output_dir / "comps_statistics.csv"
            if stat_path.is_file():
                header = read_header(stat_path)
                missing = [column for column in REQUIRED_STAT_COLUMNS if column not in header]
                if missing:
                    errors.append(f"{pack_name} comps_statistics.csv missing columns: {', '.join(missing)}")
                with stat_path.open(newline="", encoding="utf-8") as handle:
                    stat_rows = list(csv.DictReader(handle))
                stat_metrics = {row.get("metric") for row in stat_rows}
                for metric in ["return_5d", "return_20d"]:
                    if metric in stat_metrics:
                        errors.append(f"{pack_name} comps_statistics.csv must not rank {metric}")

            summary_path = output_dir / "comps_summary.md"
            if summary_path.is_file():
                summary = summary_path.read_text(encoding="utf-8")
                for section in REQUIRED_SUMMARY_SECTIONS:
                    if section not in summary:
                        errors.append(f"{pack_name} comps_summary.md missing section {section}")

    return errors


def main() -> int:
    errors = validate_comps_generator()
    if errors:
        print(f"FAIL - {len(errors)} A-share comps generator issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share comps generator checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
