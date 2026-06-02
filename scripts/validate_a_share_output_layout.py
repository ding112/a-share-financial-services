#!/usr/bin/env python3
"""Validate local A-share artifact output paths."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from a_share_output_paths import safe_filename, stage_dir, topic_name

STAGES = ("research-pack", "comps", "workbook", "handoff", "note")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", required=True, help="Chinese theme name used for the output root.")
    parser.add_argument(
        "--root",
        default=".",
        help="Workspace or run root containing the out/ directory. Defaults to the current directory.",
    )
    parser.add_argument(
        "--require-note",
        action="store_true",
        help="Require the canonical note files and manifest under out/<theme>/note/.",
    )
    return parser.parse_args()


def forbidden_paths(root: Path, theme: str) -> list[Path]:
    topic = topic_name(theme)
    filename_topic = safe_filename(theme)
    stems = list(dict.fromkeys([topic, filename_topic]))
    out_dir = root / "out"
    paths: list[Path] = []
    for stem in stems:
        paths.extend(out_dir / f"{stem}-{stage}" for stage in STAGES)
        paths.extend(
            [
                out_dir / f"{stem}行业研究.md",
                out_dir / f"{stem}路演大纲.md",
                out_dir / f"{stem}.md",
                out_dir / f"{stem}.pptx",
            ]
        )
    return paths


def expected_note_files(root: Path, theme: str) -> list[Path]:
    filename_theme = safe_filename(theme)
    note_dir = root / stage_dir(theme, "note")
    return [
        note_dir / f"{filename_theme}行业研究.md",
        note_dir / f"{filename_theme}路演大纲.md",
        note_dir / "research_assembly_manifest.json",
    ]


def validate_layout(root: Path, theme: str, require_note: bool) -> list[str]:
    errors: list[str] = []
    for path in forbidden_paths(root, theme):
        if path.exists():
            errors.append(f"forbidden A-share output path exists: {path.relative_to(root)}")

    if require_note:
        for path in expected_note_files(root, theme):
            if not path.is_file():
                errors.append(f"missing canonical A-share note output: {path.relative_to(root)}")

    return errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    errors = validate_layout(root, args.theme, args.require_note)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"OK - A-share output layout valid for {topic_name(args.theme)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
