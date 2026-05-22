#!/usr/bin/env python3
"""Validate the A-share public data fetcher without network access."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/fetch_a_share_public_data.py"
FIXTURE_PACK = ROOT / "fixtures/a-share-research-packs/robotics-reducer"
PREP_SCRIPT = ROOT / "scripts/prepare_a_share_research_pack.py"
COMPS_SCRIPT = ROOT / "scripts/generate_a_share_comps_artifacts.py"

REQUIRED_TOKENS = [
    "def parse_args",
    "def normalize_a_share_code",
    "def eastmoney_secid",
    "def read_peer_universe",
    "def fetch_market_snapshot",
    "def fetch_financial_summary",
    "def write_source_manifest",
    "def write_fetch_errors",
    "def main",
    "--peer-universe",
    "--output-dir",
    "--as-of",
    "--market-source",
    "--financial-source",
    "market_snapshot.csv",
    "financial_summary.csv",
    "source_manifest.json",
    "fetch_errors.csv",
]

REQUIRED_MARKET_COLUMNS = [
    "code",
    "price",
    "pct_change",
    "amount",
    "turnover_rate",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "snapshot_time",
    "basis",
]

REQUIRED_FINANCIAL_COLUMNS = [
    "code",
    "period",
    "revenue",
    "revenue_growth",
    "net_profit",
    "deducted_net_profit",
    "gross_margin",
    "net_margin",
    "roe",
    "asset_liability_ratio",
    "operating_cash_flow",
    "basis",
]


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_a_share_public_data", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fetch_a_share_public_data module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)


def validate_public_data_fetcher() -> list[str]:
    errors: list[str] = []
    if not SCRIPT.is_file():
        return [f"missing public data fetcher: {SCRIPT.relative_to(ROOT)}"]

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
    for token in [
        "--peer-universe",
        "--output-dir",
        "--as-of",
        "--market-source",
        "--financial-source",
    ]:
        if token not in result.stdout:
            errors.append(f"{SCRIPT.relative_to(ROOT)} --help missing {token}")

    module = load_module()
    expected_codes = {
        "300750": "300750.SZ",
        "300750.SZ": "300750.SZ",
        "600519": "600519.SH",
        "688017": "688017.SH",
        "430047": "430047.BJ",
    }
    for raw, expected in expected_codes.items():
        observed = module.normalize_a_share_code(raw)
        if observed != expected:
            errors.append(f"normalize_a_share_code({raw!r}) returned {observed!r}")

    expected_secids = {
        "300750.SZ": "0.300750",
        "600519.SH": "1.600519",
        "688017.SH": "1.688017",
        "430047.BJ": "0.430047",
    }
    for code, expected in expected_secids.items():
        observed = module.eastmoney_secid(code)
        if observed != expected:
            errors.append(f"eastmoney_secid({code!r}) returned {observed!r}")

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "public-data"
        smoke = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--peer-universe",
                str(FIXTURE_PACK / "peer_universe.csv"),
                "--output-dir",
                str(output_dir),
                "--as-of",
                "2026-05-21 15:00:00",
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
            "market_snapshot.csv",
            "financial_summary.csv",
            "source_manifest.json",
            "fetch_errors.csv",
        ]:
            if not (output_dir / filename).is_file():
                errors.append(f"fixture output missing {filename}")

        market_path = output_dir / "market_snapshot.csv"
        if market_path.is_file():
            header = read_header(market_path)
            missing = [column for column in REQUIRED_MARKET_COLUMNS if column not in header]
            if missing:
                errors.append(f"market_snapshot.csv missing columns: {', '.join(missing)}")

        financial_path = output_dir / "financial_summary.csv"
        if financial_path.is_file():
            header = read_header(financial_path)
            missing = [
                column for column in REQUIRED_FINANCIAL_COLUMNS if column not in header
            ]
            if missing:
                errors.append(f"financial_summary.csv missing columns: {', '.join(missing)}")

        manifest_path = output_dir / "source_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = {item.get("file") for item in manifest.get("files", [])}
            for filename in ["market_snapshot.csv", "financial_summary.csv"]:
                if filename not in files:
                    errors.append(f"source_manifest.json missing {filename}")

        research_pack = Path(tmp) / "research-pack"
        prep = subprocess.run(
            [
                sys.executable,
                str(PREP_SCRIPT),
                "--input-dir",
                str(output_dir),
                "--output-dir",
                str(research_pack),
                "--theme",
                "机器人产业链",
                "--as-of",
                "2026-05-21 15:00:00",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if prep.returncode != 0:
            errors.append(
                f"{PREP_SCRIPT.relative_to(ROOT)} fetched-output smoke exited "
                f"{prep.returncode}: {prep.stderr.strip()}"
            )

        comps_dir = Path(tmp) / "comps"
        comps = subprocess.run(
            [
                sys.executable,
                str(COMPS_SCRIPT),
                "--research-pack",
                str(research_pack),
                "--output-dir",
                str(comps_dir),
                "--theme",
                "机器人产业链",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if comps.returncode != 0:
            errors.append(
                f"{COMPS_SCRIPT.relative_to(ROOT)} fetched-pack smoke exited "
                f"{comps.returncode}: {comps.stderr.strip()}"
            )
        if not (comps_dir / "comps_main.csv").is_file():
            errors.append("fetched-pack comps output missing comps_main.csv")

    return errors


def main() -> int:
    errors = validate_public_data_fetcher()
    if errors:
        print(f"FAIL - {len(errors)} A-share public data fetcher issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share public data fetcher checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
