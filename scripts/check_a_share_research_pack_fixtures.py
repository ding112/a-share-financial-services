#!/usr/bin/env python3
"""Validate A-share research-pack fixtures."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures/a-share-research-packs"

REQUIRED_PACKS = [
    "robotics-reducer",
    "cpo-optical-module",
    "low-altitude-economy",
]

REQUIRED_FILES = [
    "source_manifest.json",
    "peer_universe.csv",
    "company_exposure.md",
    "events_and_risks.md",
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

MARKET_COLUMNS = [
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
    "return_5d",
    "return_20d",
    "return_basis",
    "snapshot_time",
    "basis",
]

FINANCIAL_COLUMNS = [
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _require_columns(path: Path, required: list[str], errors: list[str]) -> None:
    rows = _read_csv(path)
    if not rows:
        errors.append(f"{path.relative_to(ROOT)} has no data rows")
        return
    missing = [column for column in required if column not in rows[0]]
    if missing:
        errors.append(f"{path.relative_to(ROOT)} missing columns: {', '.join(missing)}")


def validate_fixtures() -> list[str]:
    errors: list[str] = []

    for pack in REQUIRED_PACKS:
        pack_dir = FIXTURE_ROOT / pack
        if not pack_dir.is_dir():
            errors.append(f"missing fixture pack: {pack_dir.relative_to(ROOT)}")
            continue

        for filename in REQUIRED_FILES:
            if not (pack_dir / filename).is_file():
                errors.append(f"{pack_dir.relative_to(ROOT)} missing {filename}")

        manifest_path = pack_dir / "source_manifest.json"
        if manifest_path.is_file():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = data.get("files")
            if not isinstance(files, list) or not files:
                errors.append(f"{manifest_path.relative_to(ROOT)} must contain non-empty files array")
            else:
                manifest_files = {item.get("file") for item in files if isinstance(item, dict)}
                if "peer_universe.csv" not in manifest_files:
                    errors.append(f"{manifest_path.relative_to(ROOT)} must reference peer_universe.csv")

        peer_path = pack_dir / "peer_universe.csv"
        if peer_path.is_file():
            _require_columns(peer_path, PEER_COLUMNS, errors)
            rows = _read_csv(peer_path)
            if not 8 <= len(rows) <= 15:
                errors.append(f"{peer_path.relative_to(ROOT)} must contain 8 to 15 peers")

        market_path = pack_dir / "market_snapshot.csv"
        if market_path.is_file():
            _require_columns(market_path, MARKET_COLUMNS, errors)

        financial_path = pack_dir / "financial_summary.csv"
        if financial_path.is_file():
            _require_columns(financial_path, FINANCIAL_COLUMNS, errors)

        exposure_text = (pack_dir / "company_exposure.md").read_text(encoding="utf-8") if (pack_dir / "company_exposure.md").is_file() else ""
        risk_text = (pack_dir / "events_and_risks.md").read_text(encoding="utf-8") if (pack_dir / "events_and_risks.md").is_file() else ""
        for required_phrase in ["来源类型:", "来源名称:", "数据时间:", "验证状态:"]:
            if exposure_text and required_phrase not in exposure_text:
                errors.append(f"{(pack_dir / 'company_exposure.md').relative_to(ROOT)} missing {required_phrase}")
            if risk_text and required_phrase not in risk_text:
                errors.append(f"{(pack_dir / 'events_and_risks.md').relative_to(ROOT)} missing {required_phrase}")

    return errors


def main() -> int:
    errors = validate_fixtures()
    if errors:
        print(f"FAIL - {len(errors)} A-share research-pack fixture issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share research-pack fixtures checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
