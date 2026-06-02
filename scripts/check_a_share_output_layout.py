#!/usr/bin/env python3
"""Validate A-share output layout guardrails."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_a_share_output_layout.py"
README = ROOT / "README.md"
AGENT_PROMPT = ROOT / "plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md"
NOTE_WRITER = ROOT / "managed-agent-cookbooks/a-share-market-researcher/subagents/note-writer.yaml"

THEME = "机器人产业链"


def validate_output_layout() -> list[str]:
    errors: list[str] = []

    if not SCRIPT.is_file():
        errors.append(f"missing output layout validator: {SCRIPT.relative_to(ROOT)}")
        return errors

    text = SCRIPT.read_text(encoding="utf-8")
    for token in [
        "def parse_args",
        "def forbidden_paths",
        "def expected_note_files",
        "def validate_layout",
        "--theme",
        "--root",
        "--require-note",
    ]:
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
    for token in ["--theme", "--root", "--require-note"]:
        if token not in help_result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        note_dir = root / "out" / THEME / "note"
        note_dir.mkdir(parents=True)
        (note_dir / f"{THEME}行业研究.md").write_text("# note\n", encoding="utf-8")
        (note_dir / f"{THEME}路演大纲.md").write_text("# outline\n", encoding="utf-8")
        (note_dir / "research_assembly_manifest.json").write_text("{}\n", encoding="utf-8")

        ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--theme", THEME, "--root", str(root), "--require-note"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if ok.returncode != 0:
            errors.append(f"valid output layout failed: {ok.stderr.strip()}")

        bad_file = root / "out" / f"{THEME}行业研究.md"
        bad_file.write_text("# bad\n", encoding="utf-8")
        bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--theme", THEME, "--root", str(root), "--require-note"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if bad.returncode == 0:
            errors.append("validator should reject flat Chinese note filename under out/")
        if str(bad_file.relative_to(root)) not in bad.stderr:
            errors.append("validator should report the rejected flat note path")

        slash_theme = "CPO/光模块"
        slash_note_dir = root / "out" / "CPO" / "光模块" / "note"
        slash_note_dir.mkdir(parents=True)
        (slash_note_dir / "CPO光模块行业研究.md").write_text("# note\n", encoding="utf-8")
        (slash_note_dir / "CPO光模块路演大纲.md").write_text("# outline\n", encoding="utf-8")
        (slash_note_dir / "research_assembly_manifest.json").write_text("{}\n", encoding="utf-8")
        slash_ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--theme", slash_theme, "--root", str(root), "--require-note"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if slash_ok.returncode != 0:
            errors.append(f"validator should accept sanitized note filenames: {slash_ok.stderr.strip()}")

        slash_bad_file = root / "out" / "CPO光模块行业研究.md"
        slash_bad_file.write_text("# bad\n", encoding="utf-8")
        slash_bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--theme", slash_theme, "--root", str(root), "--require-note"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if slash_bad.returncode == 0:
            errors.append("validator should reject sanitized flat note filename under out/")
        if str(slash_bad_file.relative_to(root)) not in slash_bad.stderr:
            errors.append("validator should report the rejected sanitized flat note path")

    readme_text = README.read_text(encoding="utf-8")
    if f"./out/{THEME}行业研究.md" in readme_text:
        errors.append("README.md example should not use flat note output path")
    for token in [
        f"./out/{THEME}/note/{THEME}行业研究.md",
        f"./out/{THEME}/note/{THEME}路演大纲.md",
    ]:
        if token not in readme_text:
            errors.append(f"README.md missing canonical output example `{token}`")

    for path in [AGENT_PROMPT, NOTE_WRITER]:
        content = path.read_text(encoding="utf-8")
        if "validate_a_share_output_layout.py" not in content:
            errors.append(f"{path.relative_to(ROOT)} should require output layout validation")

    return errors


def main() -> int:
    errors = validate_output_layout()
    if errors:
        print("FAIL - A-share output layout check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK - A-share output layout checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
