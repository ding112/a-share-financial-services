#!/usr/bin/env python3
"""Validate the A-share dashboard generator."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPS_SCRIPT = ROOT / "scripts/generate_a_share_comps_artifacts.py"
HANDOFF_SCRIPT = ROOT / "scripts/generate_a_share_research_handoff.py"
NOTE_SCRIPT = ROOT / "scripts/generate_a_share_research_note.py"
DASHBOARD_SCRIPT = ROOT / "scripts/generate_a_share_dashboard.py"
FIXTURE_PACK = ROOT / "fixtures/a-share-research-packs/robotics-reducer"

REQUIRED_TOKENS = [
    "def parse_args",
    "def read_csv",
    "def read_json",
    "def to_number",
    "def format_money",
    "def format_percent",
    "def sanitize_remote_url_text",
    "def render_markdown_preview",
    "def render_markdown_notes",
    "def build_stock_rows",
    "def render_stock_table",
    "def render_comps_table",
    "def render_scatter",
    "def render_sources",
    "def load_dashboard_inputs",
    "def build_html",
    "def write_dashboard",
    "def main",
    "--theme",
    "--research-pack",
    "--comps-dir",
    "--handoff-dir",
    "--note-dir",
    "--output-dir",
    "index.html",
]

REQUIRED_HTML_TEXT = [
    "A 股研究看板",
    "股票池",
    "Comps",
    "研究笔记",
    "风险与来源",
    "来源缺失",
    "净利率",
    "毛利率",
    "亿",
]

FORBIDDEN_HTML_TEXT = [
    "https://",
    "http://",
    "cdn.",
    "unpkg.com",
    "jsdelivr",
    "vite",
    "react",
]


def run_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)


def validate_dashboard() -> list[str]:
    errors: list[str] = []
    if not DASHBOARD_SCRIPT.is_file():
        return [f"missing dashboard generator: {DASHBOARD_SCRIPT.relative_to(ROOT)}"]

    text = DASHBOARD_SCRIPT.read_text(encoding="utf-8")
    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"{DASHBOARD_SCRIPT.relative_to(ROOT)} missing token `{token}`")

    help_result = run_command([sys.executable, str(DASHBOARD_SCRIPT), "--help"], ROOT)
    if help_result.returncode != 0:
        errors.append(f"{DASHBOARD_SCRIPT.relative_to(ROOT)} --help exited {help_result.returncode}")
    for token in ["--theme", "--research-pack", "--comps-dir", "--handoff-dir", "--note-dir", "--output-dir"]:
        if token not in help_result.stdout:
            errors.append(f"{DASHBOARD_SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        topic_dir = tmp_dir / "机器人产业链"
        comps_dir = topic_dir / "comps"
        handoff_dir = topic_dir / "handoff"
        note_dir = topic_dir / "note"
        dashboard_dir = topic_dir / "dashboard"

        setup_steps = [
            [
                sys.executable,
                str(COMPS_SCRIPT),
                "--research-pack",
                str(FIXTURE_PACK),
                "--output-dir",
                str(comps_dir),
                "--theme",
                "机器人产业链",
            ],
            [
                sys.executable,
                str(HANDOFF_SCRIPT),
                "--research-pack",
                str(FIXTURE_PACK),
                "--comps-dir",
                str(comps_dir),
                "--output-dir",
                str(handoff_dir),
                "--theme",
                "机器人产业链",
            ],
            [
                sys.executable,
                str(NOTE_SCRIPT),
                "--research-pack",
                str(FIXTURE_PACK),
                "--comps-dir",
                str(comps_dir),
                "--handoff-dir",
                str(handoff_dir),
                "--output-dir",
                str(note_dir),
                "--theme",
                "机器人产业链",
                "--angle",
                "关注减速器国产替代和机器人量产弹性",
                "--as-of",
                "2026-05-18",
            ],
        ]
        for step in setup_steps:
            result = run_command(step, ROOT)
            if result.returncode != 0:
                errors.append(f"{Path(step[1]).name} exited {result.returncode}: {result.stderr.strip()}")
                return errors

        (note_dir / "remote-url-smoke.md").write_text(
            "# URL 脱敏测试\n\n- 原始链接: https://example.com/research\n",
            encoding="utf-8",
        )
        dashboard_result = run_command(
            [
                sys.executable,
                str(DASHBOARD_SCRIPT),
                "--theme",
                "机器人产业链",
                "--research-pack",
                str(FIXTURE_PACK),
                "--comps-dir",
                str(comps_dir),
                "--handoff-dir",
                str(handoff_dir),
                "--note-dir",
                str(note_dir),
            ],
            tmp_dir,
        )
        if dashboard_result.returncode != 0:
            errors.append(f"{DASHBOARD_SCRIPT.name} exited {dashboard_result.returncode}: {dashboard_result.stderr.strip()}")
            return errors

        dashboard_dir = tmp_dir / "out" / "机器人产业链" / "dashboard"
        html_path = dashboard_dir / "index.html"
        if not html_path.is_file():
            errors.append("dashboard smoke output missing index.html")
            return errors

        html_text = html_path.read_text(encoding="utf-8")
        for token in REQUIRED_HTML_TEXT:
            if token not in html_text:
                errors.append(f"dashboard index.html missing text `{token}`")
        for token in FORBIDDEN_HTML_TEXT:
            if token in html_text:
                errors.append(f"dashboard index.html should not include external dependency marker `{token}`")

    return errors


def main() -> int:
    errors = validate_dashboard()
    if errors:
        print("FAIL - A-share dashboard generator check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK - A-share dashboard generator checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
