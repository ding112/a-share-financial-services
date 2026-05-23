#!/usr/bin/env python3
"""Validate A-share auxiliary fetchers without network access."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MISSING = "来源缺失"


class FakeFrame:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def to_dict(self, orient: str) -> list[dict[str, Any]]:
        if orient != "records":
            raise ValueError(f"unsupported orient: {orient}")
        return self._records


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def with_fake_akshare(fake: object):
    original = sys.modules.get("akshare")
    sys.modules["akshare"] = fake
    return original


def restore_akshare(original: object | None) -> None:
    if original is None:
        sys.modules.pop("akshare", None)
    else:
        sys.modules["akshare"] = original


def validate_auxiliary_fetchers() -> list[str]:
    errors: list[str] = []

    events = load_module(
        "fetch_a_share_events_risks",
        ROOT / "scripts/fetch_a_share_events_risks.py",
    )
    requested_dates: list[str] = []

    def stock_tfp_em(date: str):
        requested_dates.append(date)
        return FakeFrame([{"代码": "300750", "名称": "宁德时代", "备注": "停牌"}])

    fake_events_akshare = types.SimpleNamespace(
        stock_tfp_em=stock_tfp_em,
        stock_restricted_release_summary_em=lambda: FakeFrame(
            [{"股票代码": "300750", "解禁日期": "2026-02-01", "解禁股数": "100", "占总股本比例": "1"}]
        ),
    )
    original = with_fake_akshare(fake_events_akshare)
    try:
        suspension = events.fetch_suspension(["300750.SZ"], "2026-01-15")
        if requested_dates != ["20260115"]:
            errors.append("fetch_suspension should query AkShare with --as-of date")
        if not suspension.get("300750.SZ"):
            errors.append("fetch_suspension should preserve matching suspension rows")

        restricted = events.fetch_restricted_release(["300750.SZ"], "2026-01-15")
        if not restricted.get("300750.SZ"):
            errors.append("fetch_restricted_release should compare release dates to --as-of")
    except TypeError as exc:
        errors.append(f"event fetchers should accept as_of argument: {exc}")
    finally:
        restore_akshare(original)

    northbound = load_module(
        "fetch_a_share_northbound_margin",
        ROOT / "scripts/fetch_a_share_northbound_margin.py",
    )
    margin_windows: list[tuple[str, str]] = []

    def stock_margin_sse(start_date: str, end_date: str):
        margin_windows.append((start_date, end_date))
        return FakeFrame([{"信用交易日期": end_date, "融资余额(元)": "10"}])

    original = with_fake_akshare(types.SimpleNamespace(stock_margin_sse=stock_margin_sse))
    try:
        northbound.fetch_margin_summary("2025-04-20")
        if margin_windows != [("20250321", "20250420")]:
            errors.append(
                "fetch_margin_summary should derive a 30-day window ending at --as-of"
            )
    except TypeError as exc:
        errors.append(f"fetch_margin_summary should accept as_of argument: {exc}")
    finally:
        restore_akshare(original)

    index_valuation = load_module(
        "fetch_a_share_index_valuation",
        ROOT / "scripts/fetch_a_share_index_valuation.py",
    )
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        (output_dir / "source_manifest.json").write_text('{"files": []}\n', encoding="utf-8")
        index_valuation.write_source_manifest_entry(output_dir, "2026-05-22")
        manifest = json.loads((output_dir / "source_manifest.json").read_text(encoding="utf-8"))
        files = {item.get("file") for item in manifest.get("files", [])}
        for filename in ["index_valuation.csv", "market_pe_pb.csv", "index_spot.csv"]:
            if filename not in files:
                errors.append(f"index valuation manifest missing {filename}")

    company_details = load_module(
        "fetch_a_share_company_details",
        ROOT / "scripts/fetch_a_share_company_details.py",
    )
    original = with_fake_akshare(
        types.SimpleNamespace(stock_profile_cninfo=lambda symbol: FakeFrame([]))
    )
    try:
        profile = company_details.fetch_company_profile("300750.SZ")
        for field in [
            "company_name",
            "industry",
            "registered_capital",
            "established_date",
            "listing_date",
            "business_scope",
        ]:
            if profile.get(field) != MISSING:
                errors.append(f"fetch_company_profile should mark {field} as 来源缺失")
    finally:
        restore_akshare(original)

    auto_prepare = load_module(
        "auto_prepare_a_share_research_pack",
        ROOT / "scripts/auto_prepare_a_share_research_pack.py",
    )
    for filename in [
        "events_and_risks.md",
        "market_context_fund_flow.csv",
        "market_context_board_changes.csv",
        "market_context_limit_up.csv",
        "market_context_stock_fund_flow.csv",
        "macro_context.csv",
        "company_details.csv",
        "northbound_flow.csv",
        "northbound_holdings.csv",
        "margin_trading.csv",
        "board_sector_context.csv",
        "fund_heavy_stocks.csv",
        "etf_list.csv",
        "index_valuation.csv",
        "market_pe_pb.csv",
        "index_spot.csv",
    ]:
        if filename not in auto_prepare.AUTO_OUTPUTS:
            errors.append(f"AUTO_OUTPUTS missing {filename}")

    return errors


def main() -> int:
    errors = validate_auxiliary_fetchers()
    if errors:
        print(f"FAIL - {len(errors)} A-share auxiliary fetcher issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share auxiliary fetchers checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
