#!/usr/bin/env python3
"""Validate the A-share comps workbook generator."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPS_SCRIPT = ROOT / "scripts/generate_a_share_comps_artifacts.py"
WORKBOOK_SCRIPT = ROOT / "scripts/generate_a_share_comps_workbook.py"

FIXTURE_PACKS = [
    ("robotics-reducer", "机器人产业链"),
    ("cpo-optical-module", "CPO 光模块"),
    ("low-altitude-economy", "低空经济"),
]

REQUIRED_TOKENS = [
    "def parse_args",
    "def read_csv",
    "def sheet_xml",
    "def workbook_xml",
    "def workbook_relationships_xml",
    "def content_types_xml",
    "def write_workbook",
    "def main",
    "--comps-dir",
    "--output",
    "--theme",
    "Comps Main",
    "Source Notes",
    "Exceptions",
    "Statistics",
    "Data Gaps",
    "Summary",
]

REQUIRED_ZIP_MEMBERS = [
    "[Content_Types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet2.xml",
    "xl/worksheets/sheet3.xml",
    "xl/worksheets/sheet4.xml",
    "xl/worksheets/sheet5.xml",
    "xl/worksheets/sheet6.xml",
]


def validate_comps_workbook() -> list[str]:
    errors: list[str] = []
    if not WORKBOOK_SCRIPT.is_file():
        return [f"missing comps workbook generator: {WORKBOOK_SCRIPT.relative_to(ROOT)}"]

    text = WORKBOOK_SCRIPT.read_text(encoding="utf-8")
    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"{WORKBOOK_SCRIPT.relative_to(ROOT)} missing token `{token}`")

    help_result = subprocess.run(
        [sys.executable, str(WORKBOOK_SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if help_result.returncode != 0:
        errors.append(f"{WORKBOOK_SCRIPT.relative_to(ROOT)} --help exited {help_result.returncode}")
    for token in ["--comps-dir", "--output", "--theme"]:
        if token not in help_result.stdout:
            errors.append(f"{WORKBOOK_SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for pack_name, theme in FIXTURE_PACKS:
            pack_dir = ROOT / "fixtures/a-share-research-packs" / pack_name
            topic_dir = tmp_dir / theme
            comps_dir = topic_dir / "comps"
            workbook_path = topic_dir / "workbook" / f"{theme}可比公司.xlsx"

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
                errors.append(f"comps setup failed for {pack_name}: {comps.stderr.strip()}")
                continue

            workbook = subprocess.run(
                [
                    sys.executable,
                    str(WORKBOOK_SCRIPT),
                    "--comps-dir",
                    str(comps_dir),
                    "--output",
                    str(workbook_path),
                    "--theme",
                    theme,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if workbook.returncode != 0:
                errors.append(f"workbook generation failed for {pack_name}: {workbook.stderr.strip()}")
                continue
            if not workbook_path.is_file():
                errors.append(f"{pack_name} workbook output missing")
                continue

            with zipfile.ZipFile(workbook_path) as archive:
                names = set(archive.namelist())
                for member in REQUIRED_ZIP_MEMBERS:
                    if member not in names:
                        errors.append(f"{pack_name} workbook missing {member}")
                workbook_xml_text = archive.read("xl/workbook.xml").decode("utf-8")
                for sheet_name in [
                    "Comps Main",
                    "Source Notes",
                    "Exceptions",
                    "Statistics",
                    "Data Gaps",
                    "Summary",
                ]:
                    if sheet_name not in workbook_xml_text:
                        errors.append(f"{pack_name} workbook missing sheet name {sheet_name}")
                worksheet_text = "".join(
                    archive.read(f"xl/worksheets/sheet{index}.xml").decode("utf-8")
                    for index in range(1, 7)
                )
                if "来源缺失" not in worksheet_text and "口径不可比" not in worksheet_text:
                    errors.append(f"{pack_name} workbook does not preserve data quality markers")

    return errors


def main() -> int:
    errors = validate_comps_workbook()
    if errors:
        print("FAIL - A-share comps workbook check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK - A-share comps workbook checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
