#!/usr/bin/env python3
"""Validate the A-share research note assembly generator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPS_SCRIPT = ROOT / "scripts/generate_a_share_comps_artifacts.py"
HANDOFF_SCRIPT = ROOT / "scripts/generate_a_share_research_handoff.py"
NOTE_SCRIPT = ROOT / "scripts/generate_a_share_research_note.py"

FIXTURE_PACKS = [
    ("robotics-reducer", "机器人产业链", "关注减速器国产替代和机器人量产弹性"),
    ("cpo-optical-module", "CPO 光模块", "关注 AI 算力链路中的光模块环节"),
    ("low-altitude-economy", "低空经济", "关注政策催化和商业化验证节奏"),
]

REQUIRED_TOKENS = [
    "def parse_args",
    "def read_csv",
    "def read_text_file",
    "def safe_filename",
    "def load_research_inputs",
    "def build_note",
    "def build_slide_outline",
    "def write_manifest",
    "def main",
    "--research-pack",
    "--comps-dir",
    "--handoff-dir",
    "--output-dir",
    "--theme",
    "--angle",
    "--as-of",
    "行业研究.md",
    "路演大纲.md",
    "research_assembly_manifest.json",
]

REQUIRED_NOTE_SECTIONS = [
    "## 结论摘要",
    "## 行业和主题概览",
    "## 竞争格局",
    "## 可比公司分析",
    "## 想法清单",
    "## 风险和待验证事项",
    "## 来源和口径",
]

REQUIRED_SLIDE_SECTIONS = [
    "## Slide 1：主题和结论",
    "## Slide 2：为什么是现在",
    "## Slide 3：产业链和竞争格局",
    "## Slide 4：可比公司和估值口径",
    "## Slide 5：想法清单",
    "## Slide 6：风险和待验证问题",
]


def validate_research_note() -> list[str]:
    errors: list[str] = []
    if not NOTE_SCRIPT.is_file():
        return [f"missing research note generator: {NOTE_SCRIPT.relative_to(ROOT)}"]

    text = NOTE_SCRIPT.read_text(encoding="utf-8")
    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"{NOTE_SCRIPT.relative_to(ROOT)} missing token `{token}`")

    help_result = subprocess.run(
        [sys.executable, str(NOTE_SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if help_result.returncode != 0:
        errors.append(f"{NOTE_SCRIPT.relative_to(ROOT)} --help exited {help_result.returncode}")
    for token in ["--research-pack", "--comps-dir", "--handoff-dir", "--output-dir", "--theme", "--angle"]:
        if token not in help_result.stdout:
            errors.append(f"{NOTE_SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for pack_name, theme, angle in FIXTURE_PACKS:
            pack_dir = ROOT / "fixtures/a-share-research-packs" / pack_name
            topic_dir = tmp_dir / theme
            comps_dir = topic_dir / "comps"
            handoff_dir = topic_dir / "handoff"
            note_dir = topic_dir / "note"

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

            handoff = subprocess.run(
                [
                    sys.executable,
                    str(HANDOFF_SCRIPT),
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
                errors.append(f"handoff setup failed for {pack_name}: {handoff.stderr.strip()}")
                continue

            note = subprocess.run(
                [
                    sys.executable,
                    str(NOTE_SCRIPT),
                    "--research-pack",
                    str(pack_dir),
                    "--comps-dir",
                    str(comps_dir),
                    "--handoff-dir",
                    str(handoff_dir),
                    "--output-dir",
                    str(note_dir),
                    "--theme",
                    theme,
                    "--angle",
                    angle,
                    "--as-of",
                    "2026-05-18",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if note.returncode != 0:
                errors.append(f"note assembly failed for {pack_name}: {note.stderr.strip()}")
                continue

            note_path = note_dir / f"{theme}行业研究.md"
            slide_path = note_dir / f"{theme}路演大纲.md"
            manifest_path = note_dir / "research_assembly_manifest.json"

            for output_path in [note_path, slide_path, manifest_path]:
                if not output_path.is_file():
                    errors.append(f"{pack_name} missing output {output_path.name}")

            if note_path.is_file():
                note_text = note_path.read_text(encoding="utf-8")
                for section in REQUIRED_NOTE_SECTIONS:
                    if section not in note_text:
                        errors.append(f"{note_path.name} missing section {section}")
                if "来源缺失" not in note_text and "待验证" not in note_text:
                    errors.append(f"{note_path.name} must disclose missing or verification status")

            if slide_path.is_file():
                slide_text = slide_path.read_text(encoding="utf-8")
                for section in REQUIRED_SLIDE_SECTIONS:
                    if section not in slide_text:
                        errors.append(f"{slide_path.name} missing section {section}")

            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for key in ["theme", "angle", "as_of", "inputs", "outputs"]:
                    if key not in manifest:
                        errors.append(f"research_assembly_manifest.json missing key {key}")
                for value in manifest.get("outputs", {}).values():
                    if not (note_dir / value).is_file():
                        errors.append(f"manifest output does not exist: {value}")

    return errors


def main() -> int:
    errors = validate_research_note()
    if errors:
        print("FAIL - A-share research note assembly check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK - A-share research note assembly checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
