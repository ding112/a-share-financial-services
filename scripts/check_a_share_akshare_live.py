#!/usr/bin/env python3
"""Probe live AkShare A-share interfaces for a few sample companies."""

from __future__ import annotations

import argparse
import sys

from fetch_a_share_public_data import (
    fetch_akshare_financial_row,
    fetch_akshare_price_performance,
    normalize_a_share_code,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codes",
        nargs="+",
        default=["300750.SZ", "600519.SH"],
        help="A-share codes to probe.",
    )
    parser.add_argument(
        "--as-of",
        default="2026-05-22",
        help="End date used for stock_zh_a_hist price performance probe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    for raw_code in args.codes:
        code = normalize_a_share_code(raw_code)
        try:
            performance = fetch_akshare_price_performance(code, args.as_of)
            financial = fetch_akshare_financial_row(code)
        except Exception as exc:
            failures.append(f"{code}: {exc}")
            continue
        print(
            f"{code}: return_5d={performance['return_5d']}, "
            f"return_20d={performance['return_20d']}, "
            f"period={financial['period']}, revenue={financial['revenue']}"
        )

    if failures:
        print("AkShare live probe failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
