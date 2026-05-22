#!/usr/bin/env python3
"""Validate the A-share public data fetcher without network access."""

from __future__ import annotations

import csv
import contextlib
import importlib.util
import json
import types
import subprocess
import sys
import tempfile
import io
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
    "def calculate_price_performance",
    "def map_akshare_financial_summary",
    "def write_source_manifest",
    "def write_fetch_errors",
    "def run_pipeline",
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
    "return_5d",
    "return_20d",
    "return_basis",
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

    price_rows = [
        {"日期": f"2026-04-{index + 1:02d}", "收盘": str(100 + index)}
        for index in range(21)
    ]
    performance = module.calculate_price_performance(price_rows)
    if performance.get("return_5d") != "4.3478":
        errors.append(
            "calculate_price_performance should use latest qfq close versus "
            "5 trading days ago"
        )
    if performance.get("return_20d") != "20":
        errors.append(
            "calculate_price_performance should use latest qfq close versus "
            "20 trading days ago"
        )
    if "前复权收盘价" not in performance.get("return_basis", ""):
        errors.append("calculate_price_performance missing qfq return basis")

    short_performance = module.calculate_price_performance(price_rows[:5])
    if short_performance.get("return_5d") != "来源缺失":
        errors.append("calculate_price_performance should mark short 5d samples missing")
    if short_performance.get("return_20d") != "来源缺失":
        errors.append("calculate_price_performance should mark short 20d samples missing")

    financial_rows = [
        {
            "报告期": "2024-12-31",
            "营业总收入": "100",
            "营业总收入同比增长率": "5",
            "归母净利润": "10",
            "扣非净利润": "8",
            "销售毛利率": "20",
            "销售净利率": "10",
            "净资产收益率": "11",
            "资产负债率": "40",
            "经营现金流量净额": "9",
        },
        {
            "报告期": "2025-03-31",
            "营业总收入": "120",
            "营业总收入同比增长率": "6",
            "归母净利润": "12",
            "扣非净利润": "9",
            "销售毛利率": "21",
            "销售净利率": "11",
            "净资产收益率": "12",
            "资产负债率": "39",
            "经营现金流量净额": "10",
        },
    ]
    mapped = module.map_akshare_financial_summary("300750.SZ", financial_rows)
    if mapped.get("period") != "2025-03-31":
        errors.append("map_akshare_financial_summary should select latest report period")
    expected_mapped = {
        "revenue": "120",
        "revenue_growth": "6",
        "net_profit": "12",
        "deducted_net_profit": "9",
        "gross_margin": "21",
        "net_margin": "11",
        "roe": "12",
        "asset_liability_ratio": "39",
        "operating_cash_flow": "10",
    }
    for field, expected in expected_mapped.items():
        if mapped.get(field) != expected:
            errors.append(f"map_akshare_financial_summary mapped {field} to {mapped.get(field)!r}")

    wide_financial_rows = [
        {"指标": "营业总收入", "2024-12-31": "100", "2025-03-31": "120"},
        {"指标": "营业总收入同比增长率", "2024-12-31": "5", "2025-03-31": "6"},
        {"指标": "归母净利润", "2024-12-31": "10", "2025-03-31": "12"},
        {"指标": "扣非净利润", "2024-12-31": "8", "2025-03-31": "9"},
        {"指标": "销售毛利率", "2024-12-31": "20", "2025-03-31": "21"},
        {"指标": "销售净利率", "2024-12-31": "10", "2025-03-31": "11"},
        {"指标": "净资产收益率", "2024-12-31": "11", "2025-03-31": "12"},
        {"指标": "资产负债率", "2024-12-31": "40", "2025-03-31": "39"},
        {"指标": "经营现金流量净额", "2024-12-31": "9", "2025-03-31": "10"},
    ]
    wide_mapped = module.map_akshare_financial_summary("300750.SZ", wide_financial_rows)
    if wide_mapped.get("period") != "2025-03-31":
        errors.append("map_akshare_financial_summary should select latest wide-table period")
    for field, expected in expected_mapped.items():
        if wide_mapped.get(field) != expected:
            errors.append(
                f"map_akshare_financial_summary wide table mapped {field} to {wide_mapped.get(field)!r}"
            )

    def failing_fetch(_code: str) -> dict[str, str]:
        raise RuntimeError("simulated akshare outage")

    original_fetch_akshare = module.fetch_akshare_financial_row
    module.fetch_akshare_financial_row = failing_fetch
    try:
        _akshare_rows, akshare_errors = module.fetch_financial_summary(
            [{"code": "300750.SZ"}],
            "akshare",
        )
    except RuntimeError:
        pass
    else:
        errors.append("fetch_financial_summary should raise when explicit akshare source fails")
        if not akshare_errors:
            errors.append("fetch_financial_summary should preserve akshare failure details")
    finally:
        module.fetch_akshare_financial_row = original_fetch_akshare

    if hasattr(module, "run_pipeline"):
        def failing_financial_summary(_peers: list[dict[str, str]], _source: str):
            return [], [{"code": "300750.SZ", "source": "akshare", "stage": "financial_summary", "error": "boom"}]

        original_financial_summary = module.fetch_financial_summary
        module.fetch_financial_summary = failing_financial_summary
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                akshare_exit = module.run_pipeline(
                    types.SimpleNamespace(
                        peer_universe=str(FIXTURE_PACK / "peer_universe.csv"),
                        output_dir=str(Path(tempfile.mkdtemp()) / "akshare-failure"),
                        as_of="2026-05-21 15:00:00",
                        market_source="fixture",
                        financial_source="akshare",
                    )
                )
            if akshare_exit == 0:
                errors.append("run_pipeline should return non-zero for explicit akshare financial errors")
        finally:
            module.fetch_financial_summary = original_financial_summary

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
            performance_entries = [
                item
                for item in manifest.get("files", [])
                if item.get("file") == "market_snapshot.csv"
                and item.get("field_group") == "price_performance"
            ]
            if not performance_entries:
                errors.append("source_manifest.json missing market_snapshot.csv price_performance field_group")

        topic_dir = Path(tmp) / "机器人产业链"
        research_pack = topic_dir / "research-pack"
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

        comps_dir = topic_dir / "comps"
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
