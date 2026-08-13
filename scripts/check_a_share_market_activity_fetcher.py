#!/usr/bin/env python3
"""离线验证 A 股大宗交易与股东户数市场行为事实公开 CLI 契约。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FETCHER = ROOT / "scripts/fetch_a_share_market_activity.py"
AUTO_PREPARE = ROOT / "scripts/auto_prepare_a_share_research_pack.py"

BLOCK_COLUMNS = [
    "block_trade_id",
    "security_code",
    "security_name",
    "trade_date",
    "close_price_cny",
    "deal_price_cny",
    "deal_volume_shares",
    "deal_amount_cny",
    "premium_discount_pct",
    "premium_discount_pct_basis",
    "buyer_name",
    "seller_name",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]
SHAREHOLDER_COLUMNS = [
    "shareholder_snapshot_id",
    "security_code",
    "security_name",
    "statistical_end_date",
    "announcement_date",
    "holder_count",
    "previous_holder_count",
    "holder_count_change",
    "holder_count_change_basis",
    "holder_count_change_pct",
    "holder_count_change_pct_basis",
    "average_holding_shares",
    "average_holding_market_value_cny",
    "total_market_cap_cny",
    "total_shares",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]


def write_peers(path: Path, codes: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name"])
        writer.writeheader()
        for index, code in enumerate(codes):
            writer.writerow({"code": code, "name": f"样本{index + 1}"})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_fetcher(root: Path, scenario: str, codes: list[str] | None = None, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    output = root / "output"
    peers = root / "peers.csv"
    write_peers(peers, codes or ["000001.SZ", "600000.SH"])
    command = [
        sys.executable,
        str(FETCHER),
        "--peer-universe",
        str(peers),
        "--output-dir",
        str(output),
        "--as-of",
        "2026-08-13",
        "--source",
        "fixture",
        "--fixture-scenario",
        scenario,
    ]
    command.extend(extra or [])
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)


def assert_base_outputs(
    root: Path,
    errors: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    output = root / "output"
    initial_error_count = len(errors)
    for filename in (
        "block_trades.csv",
        "shareholder_counts.csv",
        "source_manifest.json",
        "fetch_errors.csv",
    ):
        if not (output / filename).is_file():
            errors.append(f"missing output: {filename}")
    if len(errors) > initial_error_count:
        return [], [], [], {}
    with (output / "block_trades.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != BLOCK_COLUMNS:
            errors.append(f"unexpected block trade columns: {reader.fieldnames}")
        block_rows = list(reader)
    with (output / "shareholder_counts.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SHAREHOLDER_COLUMNS:
            errors.append(f"unexpected shareholder columns: {reader.fieldnames}")
        shareholder_rows = list(reader)
    return (
        block_rows,
        shareholder_rows,
        read_rows(output / "fetch_errors.csv"),
        json.loads((output / "source_manifest.json").read_text(encoding="utf-8")),
    )


def validate_success(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(root, "success")
        if result.returncode != 0:
            errors.append(f"success exited {result.returncode}: {result.stderr}")
            return
        rows, shareholder_rows, notices, manifest = assert_base_outputs(root, errors)
        if not rows or not shareholder_rows:
            errors.append("success should write both market activity datasets")
            return
        if any(row["source_type"] != "public_market_data" or row["verification_status"] != "待验证" for row in rows):
            errors.append("rows must be public_market_data / 待验证")
        if any(not row["block_trade_id"].startswith("bt_") or len(row["block_trade_id"]) != 27 for row in rows):
            errors.append("block trade IDs must use bt_ plus 24 hex characters")
        if any(row["trade_date"] > "2026-08-13" for row in rows):
            errors.append("rows after as-of leaked into output")
        unit_row = next((row for row in rows if row["deal_price_cny"] == "10.5"), None)
        if not unit_row or unit_row["deal_volume_shares"] != "12000" or unit_row["deal_amount_cny"] != "126000":
            errors.append("API base units were rescaled incorrectly")
        if not any(row["premium_discount_pct_basis"] == "source" for row in rows):
            errors.append("success should retain a consistent source premium")
        if not any(row["premium_discount_pct_basis"] == "calculated" for row in rows):
            errors.append("success should calculate a missing premium")
        if any(row["buyer_name"] == "" or row["seller_name"] == "" for row in rows):
            errors.append("optional missing text must use 来源缺失, not empty strings")
        if notices:
            errors.append(f"success should not write notices: {notices}")
        if any(
            row["source_type"] != "public_market_data"
            or row["verification_status"] != "待验证"
            for row in shareholder_rows
        ):
            errors.append("shareholder rows must be public_market_data / 待验证")
        if any(
            not row["shareholder_snapshot_id"].startswith("sh_")
            or len(row["shareholder_snapshot_id"]) != 27
            for row in shareholder_rows
        ):
            errors.append("shareholder IDs must use sh_ plus 24 hex characters")
        if any(
            row["statistical_end_date"] > "2026-08-13"
            or row["announcement_date"] > "2026-08-13"
            for row in shareholder_rows
        ):
            errors.append("future shareholder snapshots leaked into output")
        unit_snapshot = next(
            (row for row in shareholder_rows if row["holder_count"] == "10000"),
            None,
        )
        if not unit_snapshot or any(
            unit_snapshot[field] != expected
            for field, expected in {
                "average_holding_shares": "19853",
                "average_holding_market_value_cny": "79215.08",
                "total_market_cap_cny": "38799544166.67",
                "total_shares": "9724196533",
            }.items()
        ):
            errors.append("shareholder API base units were rescaled incorrectly")
        if not any(
            row["holder_count_change_basis"] == "source"
            and row["holder_count_change_pct_basis"] == "source"
            for row in shareholder_rows
        ):
            errors.append("success should retain consistent source shareholder changes")
        if not any(
            row["holder_count_change_basis"] == "calculated"
            and row["holder_count_change_pct_basis"] == "calculated"
            for row in shareholder_rows
        ):
            errors.append("success should calculate missing shareholder changes")
        calculated_snapshot = next(
            (row for row in shareholder_rows if row["holder_count_change_basis"] == "calculated"),
            None,
        )
        if not calculated_snapshot or any(
            calculated_snapshot[field] != "来源缺失"
            for field in (
                "average_holding_shares",
                "average_holding_market_value_cny",
                "total_market_cap_cny",
                "total_shares",
            )
        ):
            errors.append("optional missing shareholder fields must remain 来源缺失")
        entries = [item for item in manifest.get("files", []) if item.get("file") == "block_trades.csv"]
        if len(entries) != 1:
            errors.append("manifest must contain exactly one block_trades.csv entry")
        elif any(token not in str(entries[0]) for token in ("RPT_DATA_BLOCKTRADE", "365", "50", "基础单位", "不得推断")):
            errors.append("manifest is missing report/window/unit/inference contract")
        shareholder_entries = [
            item
            for item in manifest.get("files", [])
            if item.get("file") == "shareholder_counts.csv"
        ]
        if len(shareholder_entries) != 1:
            errors.append("manifest must contain exactly one shareholder_counts.csv entry")
        elif any(
            token not in str(shareholder_entries[0])
            for token in (
                "RPT_HOLDERNUM_DET",
                "730",
                "8",
                "统计截止日",
                "公告日",
                "基础单位",
                "不得推断",
            )
        ):
            errors.append("shareholder manifest is missing visibility/unit/inference contract")


def validate_edge_scenarios(errors: list[str]) -> None:
    expectations = {
        "no-data": (0, "block_trade_no_data"),
        "all-failure": (1, "block_trade"),
        "invalid-row": (0, "block_trade"),
        "derived-conflict": (0, "block_trade"),
        "block-trade-all-failure": (0, "block_trade"),
        "shareholder-all-failure": (0, "shareholder_count"),
        "malformed-response": (1, "block_trade"),
        "all-invalid-records": (1, "block_trade"),
        "filtered-plus-invalid": (0, "block_trade"),
        "insufficient-derived": (0, None),
    }
    for scenario, (returncode, stage) in expectations.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_fetcher(root, scenario)
            if result.returncode != returncode:
                errors.append(f"{scenario} exited {result.returncode}, expected {returncode}")
                continue
            rows, shareholder_rows, notices, _ = assert_base_outputs(root, errors)
            if stage and not any(row.get("stage") == stage for row in notices):
                errors.append(f"{scenario} missing {stage} notice")
            if scenario == "no-data" and rows:
                errors.append("no-data should write an empty block trade CSV")
            if scenario == "no-data" and shareholder_rows:
                errors.append("no-data should write an empty shareholder CSV")
            if scenario == "no-data" and not any(
                row.get("stage") == "shareholder_count_no_data" for row in notices
            ):
                errors.append("no-data missing shareholder_count_no_data notice")
            if scenario == "derived-conflict":
                conflict = next((row for row in rows if row["security_code"] == "000001.SZ"), None)
                if not conflict or conflict["premium_discount_pct"] != "来源缺失" or conflict["premium_discount_pct_basis"] != "来源缺失":
                    errors.append("derived conflict must isolate premium fields")
                holder_conflicts = [
                    row
                    for row in shareholder_rows
                    if row["security_code"] == "000001.SZ"
                ]
                if len(holder_conflicts) < 2:
                    errors.append("derived conflict should expose both shareholder conflict branches")
                elif not any(
                    row["holder_count_change"] == "来源缺失"
                    and row["holder_count_change_basis"] == "来源缺失"
                    for row in holder_conflicts
                ) or not any(
                    row["holder_count_change_pct"] == "来源缺失"
                    and row["holder_count_change_pct_basis"] == "来源缺失"
                    for row in holder_conflicts
                ):
                    errors.append("shareholder conflicts must isolate the conflicting derived field")
            if scenario == "block-trade-all-failure" and not shareholder_rows:
                errors.append("shareholder success must survive complete block trade failure")
            if scenario == "shareholder-all-failure" and not rows:
                errors.append("block trade success must survive complete shareholder failure")
            if scenario == "all-invalid-records" and not any(
                row.get("stage") == "shareholder_count" for row in notices
            ):
                errors.append("all-invalid-records missing shareholder_count failure")
            if scenario in {"malformed-response", "all-invalid-records"} and any(
                row.get("stage") in {"block_trade_no_data", "shareholder_count_no_data"}
                for row in notices
            ):
                errors.append(f"{scenario} must not also report no-data")
            if scenario == "filtered-plus-invalid":
                if rows or shareholder_rows:
                    errors.append("filtered-plus-invalid should not retain unusable rows")
                for no_data_stage in ("block_trade_no_data", "shareholder_count_no_data"):
                    if not any(row.get("stage") == no_data_stage for row in notices):
                        errors.append(f"filtered-plus-invalid missing {no_data_stage}")
            if scenario == "insufficient-derived":
                if not rows or any(
                    row[field] != "来源缺失"
                    for row in rows
                    for field in ("premium_discount_pct", "premium_discount_pct_basis")
                ):
                    errors.append("insufficient block inputs must keep derived premium missing")
                if not shareholder_rows or any(
                    row[field] != "来源缺失"
                    for row in shareholder_rows
                    for field in (
                        "previous_holder_count",
                        "holder_count_change",
                        "holder_count_change_basis",
                        "holder_count_change_pct",
                        "holder_count_change_pct_basis",
                    )
                ):
                    errors.append("insufficient shareholder inputs must keep derived fields missing")


def validate_pagination_limits_duplicates(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(
            root,
            "early-stop-before-failure",
            codes=["000001.SZ"],
            extra=[
                "--block-trade-limit-per-security",
                "1",
                "--shareholder-limit-per-security",
                "1",
            ],
        )
        if result.returncode != 0:
            errors.append(f"early-stop-before-failure exited {result.returncode}: {result.stderr}")
        else:
            rows, shareholder_rows, notices, _ = assert_base_outputs(root, errors)
            if len(rows) != 1 or len(shareholder_rows) != 1:
                errors.append("valid first pages should satisfy both per-security limits")
            if any(
                row.get("stage") in {"block_trade", "shareholder_count"}
                for row in notices
            ):
                errors.append("pages after a satisfied valid-row limit must not be requested")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(
            root,
            "as-of-pagination",
            codes=["000001.SZ"],
            extra=[
                "--block-trade-limit-per-security",
                "1",
                "--shareholder-limit-per-security",
                "1",
            ],
        )
        if result.returncode != 0:
            errors.append(f"as-of-pagination exited {result.returncode}: {result.stderr}")
        else:
            rows, shareholder_rows, _, _ = assert_base_outputs(root, errors)
            if len(rows) != 1 or rows[0]["trade_date"] != "2026-08-12":
                errors.append("pagination must filter future rows before applying the limit")
            if len(shareholder_rows) != 1 or shareholder_rows[0]["announcement_date"] != "2026-08-12":
                errors.append("shareholder pagination must filter future announcements before limit")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = run_fetcher(root, "duplicate-block-trades", codes=["000001.SZ"])
        first_bytes = (root / "output/block_trades.csv").read_bytes() if first.returncode == 0 else b""
        repeated = run_fetcher(root, "duplicate-block-trades", codes=["000001.SZ"])
        rows, _, _, _ = assert_base_outputs(root, errors)
        if first.returncode != 0 or repeated.returncode != 0 or len(rows) != 2:
            errors.append("duplicate scenario must preserve two records")
        elif len({row["block_trade_id"] for row in rows}) != 2:
            errors.append("exact duplicate trades need distinct stable IDs")
        if first_bytes != (root / "output/block_trades.csv").read_bytes():
            errors.append("repeated fixture run should be byte-stable")


def validate_inputs_and_preservation(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(root, "success", codes=["200001.SZ", "000001.SZ"])
        block_rows, shareholder_rows, notices, _ = assert_base_outputs(root, errors)
        if result.returncode != 0:
            errors.append(f"partial B-share input should retain valid A-share results: {result.stderr}")
        if any(
            row["security_code"] == "200001.SZ"
            for row in [*block_rows, *shareholder_rows]
        ):
            errors.append("Shenzhen B-share codes must not enter A-share outputs")
        if not any(
            row.get("code") == "200001.SZ" and row.get("stage") == "market_activity_input"
            for row in notices
        ):
            errors.append("Shenzhen B-share input must be recorded as market_activity_input")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "output"
        output.mkdir()
        (output / "source_manifest.json").write_text('{"files":[{"file":"keep.csv"}]}\n', encoding="utf-8")
        with (output / "fetch_errors.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["code", "source", "stage", "error"])
            writer.writeheader()
            writer.writerow({"code": "KEEP", "source": "fixture", "stage": "other_stage", "error": "keep"})
        result = run_fetcher(root, "success", codes=["bad", "000001.SZ"])
        rows, shareholder_rows, notices, manifest = assert_base_outputs(root, errors)
        if result.returncode != 0 or not rows:
            errors.append("partial invalid input should retain valid results")
        if not shareholder_rows:
            errors.append("partial invalid input should retain valid shareholder results")
        if not any(row.get("stage") == "market_activity_input" for row in notices):
            errors.append("partial invalid input should write market_activity_input")
        if not any(row.get("stage") == "other_stage" for row in notices):
            errors.append("market activity run must preserve other stage errors")
        if not any(item.get("file") == "keep.csv" for item in manifest.get("files", [])):
            errors.append("market activity run must preserve other manifest entries")
    for malformed in ("missing", "no-code", "all-invalid"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            peers = root / "peers.csv"
            if malformed == "no-code":
                peers.write_text("name\n样本\n", encoding="utf-8")
            elif malformed == "all-invalid":
                write_peers(peers, ["bad"])
            command = [sys.executable, str(FETCHER), "--peer-universe", str(peers), "--output-dir", str(output), "--as-of", "2026-08-13", "--source", "fixture"]
            result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                errors.append(f"{malformed} input should fail")
            _, _, _, manifest = assert_base_outputs(root, errors)
            managed = {
                item.get("file")
                for item in manifest.get("files", [])
            }
            if not {"block_trades.csv", "shareholder_counts.csv"}.issubset(managed):
                errors.append(f"{malformed} input must retain both manifest entries")


def validate_auto_prepare(errors: list[str]) -> None:
    help_result = subprocess.run([sys.executable, str(AUTO_PREPARE), "--help"], cwd=ROOT, check=False, capture_output=True, text=True)
    for flag in (
        "--market-activity-source",
        "--market-activity-fixture-scenario",
        "--block-trade-lookback-days",
        "--block-trade-limit-per-security",
        "--shareholder-lookback-days",
        "--shareholder-limit-per-security",
        "--skip-market-activity",
    ):
        if flag not in help_result.stdout:
            errors.append(f"auto prepare help missing {flag}")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "pack"
        command = [sys.executable, str(AUTO_PREPARE), "--theme", "市场行为事实 fixture", "--output-dir", str(output), "--as-of", "2026-08-13", "--universe-source", "fixture", "--market-source", "fixture", "--financial-source", "fixture", "--research-report-source", "fixture", "--market-activity-source", "fixture", "--market-activity-fixture-scenario", "all-failure"]
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f"auto prepare should degrade optional failure: {result.stderr}")
        elif "warning: fetch_a_share_market_activity.py exited 1" not in result.stderr:
            errors.append("auto prepare should surface market activity failure warning")
        if not (output / "block_trades.csv").is_file():
            errors.append("auto prepare missing managed block_trades.csv")
        if not (output / "shareholder_counts.csv").is_file():
            errors.append("auto prepare missing managed shareholder_counts.csv")
        if (output / "auto_prepare_manifest.json").is_file():
            inputs = json.loads((output / "auto_prepare_manifest.json").read_text(encoding="utf-8")).get("inputs", {})
            for key in (
                "market_activity_source",
                "market_activity_fixture_scenario",
                "block_trade_lookback_days",
                "block_trade_limit_per_security",
                "shareholder_lookback_days",
                "shareholder_limit_per_security",
                "skip_market_activity",
            ):
                if key not in inputs:
                    errors.append(f"auto prepare manifest missing {key}")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "pack"
        command = [sys.executable, str(AUTO_PREPARE), "--theme", "跳过市场行为事实", "--output-dir", str(output), "--as-of", "2026-08-13", "--universe-source", "fixture", "--market-source", "fixture", "--financial-source", "fixture", "--research-report-source", "fixture", "--skip-market-activity"]
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f"skip market activity exited {result.returncode}: {result.stderr}")
        if (output / "block_trades.csv").exists():
            errors.append("skip market activity should not generate block trade content")
        if (output / "shareholder_counts.csv").exists():
            errors.append("skip market activity should not generate shareholder content")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "pack"
        base_command = [
            sys.executable,
            str(AUTO_PREPARE),
            "--theme",
            "强制重跑跳过市场行为事实",
            "--output-dir",
            str(output),
            "--as-of",
            "2026-08-13",
            "--universe-source",
            "fixture",
            "--market-source",
            "fixture",
            "--financial-source",
            "fixture",
            "--research-report-source",
            "fixture",
            "--market-activity-source",
            "fixture",
        ]
        initial = subprocess.run(
            base_command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        repeated = subprocess.run(
            [*base_command, "--force", "--skip-market-activity"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if initial.returncode != 0 or repeated.returncode != 0:
            errors.append(f"forced skip rerun failed: {initial.stderr}{repeated.stderr}")
        if any((output / filename).exists() for filename in ("block_trades.csv", "shareholder_counts.csv")):
            errors.append("forced skip rerun must remove stale market activity CSVs")
        manifest = json.loads((output / "source_manifest.json").read_text(encoding="utf-8"))
        if any(
            item.get("file") in {"block_trades.csv", "shareholder_counts.csv"}
            for item in manifest.get("files", [])
        ):
            errors.append("forced skip rerun must remove stale market activity manifest entries")
        notices = read_rows(output / "fetch_errors.csv")
        if any(
            row.get("stage") == "market_activity_input"
            or row.get("stage", "").startswith(("block_trade", "shareholder_count"))
            for row in notices
        ):
            errors.append("forced skip rerun must remove stale market activity errors")


def validate_market_activity_fetcher() -> list[str]:
    errors: list[str] = []
    if not FETCHER.is_file():
        errors.append(f"missing fetcher: {FETCHER.relative_to(ROOT)}")
    else:
        validate_success(errors)
        validate_edge_scenarios(errors)
        validate_pagination_limits_duplicates(errors)
        validate_inputs_and_preservation(errors)
        validate_auto_prepare(errors)
    return errors


def main() -> int:
    errors = validate_market_activity_fetcher()
    if errors:
        print(f"FAIL — {len(errors)} market activity issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  ✗ {error}", file=sys.stderr)
        return 1
    print("OK — A-share block trade and shareholder market activity checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
