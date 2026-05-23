#!/usr/bin/env python3
"""Validate the A-share auto research-pack preparation flow offline."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/auto_prepare_a_share_research_pack.py"
REQUIREMENTS = ROOT / "requirements.txt"
AGENT_PROMPT = ROOT / "plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md"
MANAGED_AGENT = ROOT / "managed-agent-cookbooks/a-share-market-researcher/agent.yaml"
DATA_PREP_AGENT = ROOT / "managed-agent-cookbooks/a-share-market-researcher/subagents/data-prep.yaml"
VERTICAL_DATA_SOURCES = (
    ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md"
)
BUNDLED_DATA_SOURCES = (
    ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md"
)
README = ROOT / "managed-agent-cookbooks/a-share-market-researcher/README.md"

REQUIRED_TOKENS = [
    "def parse_args",
    "def normalize_a_share_code",
    "def infer_exchange",
    "def infer_board",
    "def build_peer_universe",
    "def fetch_akshare_candidates",
    "def write_auto_prepare_manifest",
    "def run_public_data_fetcher",
    "def main",
    "--theme",
    "--output-dir",
    "--as-of",
    "--peer-universe",
    "--force",
    "--universe-source",
    "candidate_peer_universe.csv",
    "peer_universe.csv",
    "market_snapshot.csv",
    "financial_summary.csv",
    "source_manifest.json",
    "fetch_errors.csv",
    "auto_prepare_manifest.json",
]

PEER_COLUMNS = [
    "code",
    "name",
    "exchange",
    "board",
    "peer_group",
    "theme_role",
    "exposure_summary",
    "exposure_source_ref",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_auto_prepare() -> list[str]:
    errors: list[str] = []
    if not SCRIPT.is_file():
        return [f"missing auto prepare script: {SCRIPT.relative_to(ROOT)}"]

    text = SCRIPT.read_text(encoding="utf-8")
    for token in REQUIRED_TOKENS:
        if token not in text:
            errors.append(f"{SCRIPT.relative_to(ROOT)} missing token `{token}`")
    if "pip install" in text or "subprocess.check_call([sys.executable, \"-m\", \"pip\"" in text:
        errors.append(f"{SCRIPT.relative_to(ROOT)} must not install dependencies")

    help_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if help_result.returncode != 0:
        errors.append(f"{SCRIPT.relative_to(ROOT)} --help exited {help_result.returncode}")
    for token in ["--theme", "--output-dir", "--as-of", "--peer-universe", "--force"]:
        if token not in help_result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "机器人产业链" / "research-pack"
        smoke = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--theme",
                "机器人产业链",
                "--output-dir",
                str(output_dir),
                "--as-of",
                "2026-05-22",
                "--universe-source",
                "fixture",
                "--market-source",
                "fixture",
                "--financial-source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if smoke.returncode != 0:
            errors.append(
                f"{SCRIPT.relative_to(ROOT)} fixture smoke exited "
                f"{smoke.returncode}: {smoke.stderr.strip()}"
            )
            return errors

        for filename in [
            "candidate_peer_universe.csv",
            "peer_universe.csv",
            "market_snapshot.csv",
            "financial_summary.csv",
            "source_manifest.json",
            "fetch_errors.csv",
            "auto_prepare_manifest.json",
        ]:
            if not (output_dir / filename).is_file():
                errors.append(f"auto prepare output missing {filename}")

        peer_path = output_dir / "peer_universe.csv"
        if peer_path.is_file():
            rows = read_csv_rows(peer_path)
            if not rows:
                errors.append("peer_universe.csv is empty")
            missing_columns = [column for column in PEER_COLUMNS if column not in rows[0]]
            if missing_columns:
                errors.append(f"peer_universe.csv missing columns: {', '.join(missing_columns)}")
            if len(rows) > 15:
                errors.append("peer_universe.csv should contain at most 15 rows by default")
            if any(row.get("theme_role") != "待验证" for row in rows):
                errors.append("fixture peer_universe.csv should mark theme_role as 待验证")

        manifest_path = output_dir / "auto_prepare_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key in ["theme", "as_of", "inputs", "outputs", "selection"]:
                if key not in manifest:
                    errors.append(f"auto_prepare_manifest.json missing key `{key}`")

        second = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--theme",
                "机器人产业链",
                "--output-dir",
                str(output_dir),
                "--as-of",
                "2026-05-22",
                "--universe-source",
                "fixture",
                "--market-source",
                "fixture",
                "--financial-source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if second.returncode != 0:
            errors.append("auto prepare should reuse an existing complete research-pack")
        if "reusing existing research-pack" not in second.stdout:
            errors.append("auto prepare reuse path should announce existing research-pack reuse")

    if not REQUIREMENTS.is_file():
        errors.append("missing requirements.txt")
    elif "akshare" not in REQUIREMENTS.read_text(encoding="utf-8").lower():
        errors.append("requirements.txt must include akshare")

    if not AGENT_PROMPT.is_file():
        errors.append(f"missing {AGENT_PROMPT.relative_to(ROOT)}")
    else:
        agent_text = AGENT_PROMPT.read_text(encoding="utf-8")
        for token in [
            "tools: Read, Write, Edit, Bash",
            ".venv/bin/python scripts/auto_prepare_a_share_research_pack.py",
            "不要运行 pip install",
        ]:
            if token not in agent_text:
                errors.append(f"{AGENT_PROMPT.relative_to(ROOT)} missing `{token}`")

    if not DATA_PREP_AGENT.is_file():
        errors.append(f"missing {DATA_PREP_AGENT.relative_to(ROOT)}")
    else:
        data_prep_text = DATA_PREP_AGENT.read_text(encoding="utf-8")
        for token in ["name: data-prep", "bash", "auto_prepare_a_share_research_pack.py"]:
            if token not in data_prep_text:
                errors.append(f"{DATA_PREP_AGENT.relative_to(ROOT)} missing `{token}`")

    if MANAGED_AGENT.is_file() and "./subagents/data-prep.yaml" not in MANAGED_AGENT.read_text(
        encoding="utf-8"
    ):
        errors.append(f"{MANAGED_AGENT.relative_to(ROOT)} must register data-prep subagent")

    for source in [VERTICAL_DATA_SOURCES, BUNDLED_DATA_SOURCES, README]:
        if not source.is_file():
            errors.append(f"missing {source.relative_to(ROOT)}")
            continue
        source_text = source.read_text(encoding="utf-8")
        for token in ["auto_prepare_a_share_research_pack.py", "candidate_peer_universe.csv"]:
            if token not in source_text:
                errors.append(f"{source.relative_to(ROOT)} missing `{token}`")

    if ".venv/" not in (ROOT / ".gitignore").read_text(encoding="utf-8"):
        errors.append(".gitignore must ignore .venv/")

    return errors


def main() -> int:
    errors = validate_auto_prepare()
    if errors:
        print(f"FAIL - {len(errors)} A-share auto prepare issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share auto prepare checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
