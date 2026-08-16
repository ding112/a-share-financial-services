#!/usr/bin/env python3
"""为 A 股 research-pack 抓取资产负债表明细。

第一条财务报表明细 tracer bullet 仅覆盖沪深证券的资产负债表。它保留
来源的非空行项目，并只为口径明确的核心项目提供规范名称；不把当前来源
未声明的报表范围猜测为合并或母公司口径。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MISSING = "来源缺失"
SOURCE_NAME = "AkShare（东方财富财务报表）"
SOURCE_KEY = "financial_statement"
ERROR_COLUMNS = ["code", "source", "stage", "error"]
STATEMENT_COLUMNS = [
    "statement_item_id",
    "security_code",
    "security_name",
    "organization_type",
    "statement_type",
    "period",
    "report_type",
    "notice_date",
    "update_date",
    "currency",
    "statement_scope",
    "source_line_item",
    "normalized_line_item",
    "value",
    "unit",
    "value_semantics",
    "domestic_audit_opinion",
    "overseas_audit_opinion",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]
METADATA_FIELDS = {
    "SECUCODE",
    "SECURITY_CODE",
    "SECURITY_NAME_ABBR",
    "ORG_CODE",
    "ORG_TYPE",
    "REPORT_DATE",
    "REPORT_TYPE",
    "REPORT_DATE_NAME",
    "SECURITY_TYPE_CODE",
    "NOTICE_DATE",
    "UPDATE_DATE",
    "CURRENCY",
    "OPINION_TYPE",
    "OSOPINION_TYPE",
    "LISTING_STATE",
}
BJ_PREFIXES = (
    "430", "830", "831", "832", "833", "834", "835", "836", "837",
    "838", "839", "870", "871", "872", "873", "920",
)

CORE_MAPPINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("monetary_funds", ("MONETARYFUNDS",)),
    ("accounts_receivable", ("ACCOUNTS_RECE",)),
    ("inventory", ("INVENTORY",)),
    ("contract_assets", ("CONTRACT_ASSET",)),
    ("fixed_assets", ("FIXED_ASSET",)),
    ("construction_in_progress", ("CIP",)),
    ("intangible_assets", ("INTANGIBLE_ASSET",)),
    ("goodwill", ("GOODWILL",)),
    ("current_assets", ("TOTAL_CURRENT_ASSETS",)),
    ("total_assets", ("TOTAL_ASSETS",)),
    ("accounts_payable", ("ACCOUNTS_PAYABLE",)),
    ("contract_liabilities", ("CONTRACT_LIAB",)),
    ("short_term_borrowings", ("SHORT_LOAN",)),
    ("long_term_borrowings", ("LONG_LOAN",)),
    ("bonds_payable", ("BOND_PAYABLE",)),
    ("lease_liabilities", ("LEASE_LIAB",)),
    ("current_liabilities", ("TOTAL_CURRENT_LIAB",)),
    ("total_liabilities", ("TOTAL_LIABILITIES",)),
    ("equity_attributable_to_parent", ("TOTAL_PARENT_EQUITY", "PARENT_EQUITY_BALANCE")),
    ("minority_interests", ("MINORITY_EQUITY",)),
    ("total_equity", ("TOTAL_EQUITY",)),
)
CORE_ORDER = {name: index for index, (name, _) in enumerate(CORE_MAPPINGS)}

# 当前 AkShare 资产负债表接口公开的金额字段目录。目录是刻意显式维护的：
# 不能因为未知字段的名称或数值看起来像金额就自行猜测其单位。
KNOWN_AMOUNT_FIELDS = frozenset(
    """
    ACCEPT_DEPOSIT_INTERBANK ACCOUNTS_PAYABLE ACCOUNTS_RECE ACCRUED_EXPENSE
    ADVANCE_RECEIVABLES AGENT_TRADE_SECURITY AGENT_UNDERWRITE_SECURITY
    AMORTIZE_COST_FINASSET AMORTIZE_COST_FINLIAB AMORTIZE_COST_NCFINASSET
    AMORTIZE_COST_NCFINLIAB APPOINT_FVTPL_FINASSET APPOINT_FVTPL_FINLIAB
    ASSET_BALANCE ASSET_OTHER ASSIGN_CASH_DIVIDEND AVAILABLE_SALE_FINASSET
    BOND_PAYABLE BORROW_FUND BUY_RESALE_FINASSET CAPITAL_RESERVE CIP
    CONSUMPTIVE_BIOLOGICAL_ASSET CONTRACT_ASSET CONTRACT_LIAB CONVERT_DIFF
    CREDITOR_INVEST CURRENT_ASSET_BALANCE CURRENT_ASSET_OTHER
    CURRENT_LIAB_BALANCE CURRENT_LIAB_OTHER DEFER_INCOME DEFER_INCOME_1YEAR
    DEFER_TAX_ASSET DEFER_TAX_LIAB DERIVE_FINASSET DERIVE_FINLIAB
    DEVELOP_EXPENSE DIV_HOLDSALE_ASSET DIV_HOLDSALE_LIAB DIVIDEND_PAYABLE
    DIVIDEND_RECE EQUITY_BALANCE EQUITY_OTHER EXPORT_REFUND_RECE
    FEE_COMMISSION_PAYABLE FIN_FUND FINANCE_RECE FIXED_ASSET
    FIXED_ASSET_DISPOSAL FVTOCI_FINASSET FVTOCI_NCFINASSET FVTPL_FINASSET
    FVTPL_FINLIAB GENERAL_RISK_RESERVE GOODWILL HOLD_MATURITY_INVEST
    HOLDSALE_ASSET HOLDSALE_LIAB INSURANCE_CONTRACT_RESERVE INTANGIBLE_ASSET
    INTEREST_PAYABLE INTEREST_RECE INTERNAL_PAYABLE INTERNAL_RECE INVENTORY
    INVEST_REALESTATE LEASE_LIAB LEND_FUND LIAB_BALANCE LIAB_EQUITY_BALANCE
    LIAB_EQUITY_OTHER LIAB_OTHER LOAN_ADVANCE LOAN_PBC LONG_EQUITY_INVEST
    LONG_LOAN LONG_PAYABLE LONG_PREPAID_EXPENSE LONG_RECE
    LONG_STAFFSALARY_PAYABLE MINORITY_EQUITY MONETARYFUNDS
    NONCURRENT_ASSET_1YEAR NONCURRENT_ASSET_BALANCE NONCURRENT_ASSET_OTHER
    NONCURRENT_LIAB_1YEAR NONCURRENT_LIAB_BALANCE NONCURRENT_LIAB_OTHER
    NOTE_ACCOUNTS_PAYABLE NOTE_ACCOUNTS_RECE NOTE_PAYABLE NOTE_RECE
    OIL_GAS_ASSET OTHER_COMPRE_INCOME OTHER_CREDITOR_INVEST
    OTHER_CURRENT_ASSET OTHER_CURRENT_LIAB OTHER_EQUITY_INVEST
    OTHER_EQUITY_OTHER OTHER_EQUITY_TOOL OTHER_NONCURRENT_ASSET
    OTHER_NONCURRENT_FINASSET OTHER_NONCURRENT_LIAB OTHER_PAYABLE OTHER_RECE
    PARENT_EQUITY_BALANCE PARENT_EQUITY_OTHER PERPETUAL_BOND
    PERPETUAL_BOND_PAYBALE PREDICT_CURRENT_LIAB PREDICT_LIAB PREFERRED_SHARES
    PREFERRED_SHARES_PAYBALE PREMIUM_RECE PREPAYMENT PRODUCTIVE_BIOLOGY_ASSET
    PROJECT_MATERIAL RC_RESERVE_RECE REINSURE_PAYABLE REINSURE_RECE
    SELL_REPO_FINASSET SETTLE_EXCESS_RESERVE SHARE_CAPITAL SHORT_BOND_PAYABLE
    SHORT_FIN_PAYABLE SHORT_LOAN SPECIAL_PAYABLE SPECIAL_RESERVE
    STAFF_SALARY_PAYABLE SUBSIDY_RECE SURPLUS_RESERVE TAX_PAYABLE TOTAL_ASSETS
    TOTAL_CURRENT_ASSETS TOTAL_CURRENT_LIAB TOTAL_EQUITY TOTAL_LIAB_EQUITY
    TOTAL_LIABILITIES TOTAL_NONCURRENT_ASSETS TOTAL_NONCURRENT_LIAB
    TOTAL_OTHER_PAYABLE TOTAL_OTHER_RECE TOTAL_PARENT_EQUITY TRADE_FINASSET
    TRADE_FINASSET_NOTFVTPL TRADE_FINLIAB TRADE_FINLIAB_NOTFVTPL
    TREASURY_SHARES UNASSIGN_RPOFIT UNCONFIRM_INVEST_LOSS USERIGHT_ASSET
    """.split()
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="包含 A 股股票池的 CSV。")
    parser.add_argument("--output-dir", required=True, help="research-pack 输出目录。")
    parser.add_argument("--as-of", required=True, help="研究截止日，例如 2026-08-16。")
    parser.add_argument(
        "--period-limit",
        type=int,
        default=12,
        help="每个证券最多保留的资产负债表报告期数，默认 12。",
    )
    parser.add_argument(
        "--source",
        choices=["akshare", "fixture"],
        default="akshare",
        help="财务报表来源；fixture 仅用于离线检查。",
    )
    parser.add_argument(
        "--fixture-scenario",
        choices=["success", "no-data"],
        default="success",
        help="fixture 离线场景。",
    )
    return parser.parse_args()


def infer_exchange(symbol: str) -> str | None:
    if symbol.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if symbol.startswith(BJ_PREFIXES):
        return "BJ"
    if symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ"
    return None


def normalize_a_share_code(raw_code: str) -> str:
    value = raw_code.strip().upper()
    match = re.fullmatch(r"(\d{1,6})(?:\.(SH|SZ|BJ))?", value)
    if not match:
        raise ValueError(f"unsupported A-share code: {raw_code!r}")
    symbol = match.group(1).zfill(6)
    inferred = infer_exchange(symbol)
    supplied = match.group(2)
    if inferred is None or (supplied and supplied != inferred):
        raise ValueError(f"unsupported A-share code: {raw_code!r}")
    return f"{symbol}.{inferred}"


def error_row(code: str, stage: str, error: str) -> dict[str, str]:
    return {"code": code, "source": SOURCE_KEY, "stage": stage, "error": error}


def read_peers(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "code" not in reader.fieldnames:
            raise ValueError(f"peer universe requires code column: {path}")
        raw_rows = list(reader)
    peers: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in raw_rows:
        raw_code = str(row.get("code") or "").strip()
        try:
            code = normalize_a_share_code(raw_code)
        except ValueError as exc:
            errors.append(error_row(raw_code or MISSING, "financial_statement_input", str(exc)))
            continue
        if code in seen:
            continue
        seen.add(code)
        peers.append({"code": code, "name": str(row.get("name") or "").strip()})
    if not peers:
        raise ValueError(f"peer universe contains no valid A-share code: {path}")
    return peers, errors


def is_missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, str) and value.strip().lower() in {"nan", "none", "null", "-", "--"}:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def decimal_text(value: Any) -> str:
    if is_missing(value):
        raise ValueError("empty value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"invalid numeric value: {value!r}")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_date(value: Any, field: str) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if is_missing(value):
        raise ValueError(f"资产负债表缺少 {field}")
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"资产负债表 {field} 无法解析: {value!r}") from exc


def date_text(value: Any, field: str) -> str:
    return parse_date(value, field).isoformat()


def statement_item_id(code: str, statement_type: str, period: str, source_line_item: str) -> str:
    material = "\x1f".join((code, statement_type, period, source_line_item))
    return "fs_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def core_mapping_for_field(field: str) -> str | None:
    for normalized, candidates in CORE_MAPPINGS:
        if field in candidates:
            return normalized
    return None


def selected_core_fields(record: dict[str, Any]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for normalized, candidates in CORE_MAPPINGS:
        for field in candidates:
            if field in record and not is_missing(record[field]):
                decimal_text(record[field])
                selected[normalized] = field
                break
    return selected


def item_basis(field: str, normalized: str, unit: str) -> str:
    mapping = normalized if normalized != MISSING else "未映射来源项目"
    return (
        f"资产负债表来源字段 {field}；规范项目 {mapping}；单位 {unit}；"
        "报告期末时点值；报表范围来源缺失"
    )


def metadata_from_record(record: dict[str, Any], peer: dict[str, str]) -> dict[str, str]:
    period = date_text(record.get("REPORT_DATE"), "REPORT_DATE")
    return {
        "security_code": peer["code"],
        "security_name": str(record.get("SECURITY_NAME_ABBR") or peer["name"] or MISSING),
        "organization_type": str(record.get("ORG_TYPE") or MISSING),
        "statement_type": "balance_sheet",
        "period": period,
        "report_type": str(record.get("REPORT_TYPE") or MISSING),
        "notice_date": date_text(record.get("NOTICE_DATE"), "NOTICE_DATE"),
        "update_date": date_text(record.get("UPDATE_DATE"), "UPDATE_DATE"),
        "currency": str(record.get("CURRENCY") or MISSING),
        "statement_scope": MISSING,
        "value_semantics": "point_in_time",
        "domestic_audit_opinion": str(record.get("OPINION_TYPE") or MISSING),
        "overseas_audit_opinion": str(record.get("OSOPINION_TYPE") or MISSING),
        "source_type": "public_market_data",
        "source_name": SOURCE_NAME,
    }


def raw_item_rows(record: dict[str, Any], metadata: dict[str, str]) -> list[dict[str, str]]:
    selected = selected_core_fields(record)
    rows: list[dict[str, str]] = []
    for field in sorted(record):
        value = record[field]
        if field in METADATA_FIELDS or field.endswith("_YOY") or is_missing(value):
            continue
        if field not in KNOWN_AMOUNT_FIELDS:
            continue
        try:
            value_text = decimal_text(value)
        except ValueError:
            continue
        normalized = core_mapping_for_field(field) or MISSING
        if normalized != MISSING and selected.get(normalized) != field:
            normalized = MISSING
        row = dict(metadata)
        row.update(
            {
                "source_line_item": field,
                "normalized_line_item": normalized,
                "value": value_text,
                "unit": "CNY",
                "verification_status": "verified",
                "basis": item_basis(field, normalized, "CNY"),
            }
        )
        row["statement_item_id"] = statement_item_id(
            row["security_code"], row["statement_type"], row["period"], field
        )
        rows.append(row)
    return rows


def missing_core_rows(rows: list[dict[str, str]], metadata: dict[str, str]) -> list[dict[str, str]]:
    present = {row["normalized_line_item"] for row in rows if row["normalized_line_item"] != MISSING}
    placeholders: list[dict[str, str]] = []
    for normalized, _ in CORE_MAPPINGS:
        if normalized in present:
            continue
        source_line_item = f"core:{normalized}"
        row = dict(metadata)
        row.update(
            {
                "source_line_item": source_line_item,
                "normalized_line_item": normalized,
                "value": MISSING,
                "unit": MISSING,
                "verification_status": MISSING,
                "basis": "该资产负债表记录中未找到适用来源项目；报表范围来源缺失",
            }
        )
        row["statement_item_id"] = statement_item_id(
            row["security_code"], row["statement_type"], row["period"], source_line_item
        )
        placeholders.append(row)
    return placeholders


def normalize_record(record: dict[str, Any], peer: dict[str, str]) -> list[dict[str, str]]:
    metadata = metadata_from_record(record, peer)
    rows = raw_item_rows(record, metadata)
    return rows + missing_core_rows(rows, metadata)


def fixture_record(peer: dict[str, str], period: str, sequence: int) -> dict[str, Any]:
    amount = 1000 + sequence * 100
    record: dict[str, Any] = {
        "SECUCODE": peer["code"],
        "SECURITY_CODE": peer["code"].split(".", 1)[0],
        "SECURITY_NAME_ABBR": peer["name"],
        "ORG_CODE": f"fixture-{sequence}",
        "ORG_TYPE": "通用",
        "REPORT_DATE": f"{period} 00:00:00",
        "REPORT_TYPE": "年报",
        "REPORT_DATE_NAME": f"{period[:4]}年报",
        "SECURITY_TYPE_CODE": "058001001",
        "NOTICE_DATE": f"{int(period[:4]) + 1}-03-20 00:00:00",
        "UPDATE_DATE": f"{int(period[:4]) + 1}-03-20 00:00:00",
        "CURRENCY": "CNY",
        "OPINION_TYPE": "标准无保留意见",
        "OSOPINION_TYPE": "来源缺失",
        "LISTING_STATE": "0",
        "MONETARYFUNDS": amount + 1,
        "ACCOUNTS_RECE": amount + 2,
        "INVENTORY": amount + 3,
        "CONTRACT_ASSET": amount + 4,
        "FIXED_ASSET": amount + 5,
        "CIP": amount + 6,
        "INTANGIBLE_ASSET": amount + 7,
        "GOODWILL": amount + 8,
        "TOTAL_CURRENT_ASSETS": amount + 9,
        "TOTAL_ASSETS": amount + 10,
        "ACCOUNTS_PAYABLE": amount + 11,
        "CONTRACT_LIAB": amount + 12,
        "SHORT_LOAN": amount + 13,
        "LONG_LOAN": amount + 14,
        "BOND_PAYABLE": amount + 15,
        "LEASE_LIAB": amount + 16,
        "TOTAL_CURRENT_LIAB": amount + 17,
        "TOTAL_LIABILITIES": amount + 18,
        "TOTAL_PARENT_EQUITY": amount + 19,
        "MINORITY_EQUITY": amount + 20,
        "TOTAL_EQUITY": amount + 21,
        "MONETARYFUNDS_YOY": 8.2,
    }
    if peer["code"] == "600519.SH" and period == "2025-12-31":
        record["PARENT_EQUITY_BALANCE"] = amount + 119
    if peer["code"] == "002594.SZ" and period == "2025-12-31":
        record.pop("GOODWILL")
    return record


def fixture_records(peer: dict[str, str], scenario: str, sequence: int) -> list[dict[str, Any]]:
    if scenario == "no-data":
        return []
    return [
        fixture_record(peer, "2025-12-31", sequence),
        fixture_record(peer, "2024-12-31", sequence),
    ]


def fetch_akshare_records(code: str) -> list[dict[str, Any]]:
    import akshare as ak  # type: ignore[import-not-found]

    symbol, exchange = code.split(".", 1)
    frame = ak.stock_balance_sheet_by_report_em(symbol=f"{exchange}{symbol}")
    return list(frame.to_dict("records"))


def select_records(records: list[dict[str, Any]], as_of: dt.date, period_limit: int) -> list[dict[str, Any]]:
    eligible: list[tuple[dt.date, dict[str, Any]]] = []
    for record in records:
        period = parse_date(record.get("REPORT_DATE"), "REPORT_DATE")
        if period <= as_of:
            eligible.append((period, record))
    eligible.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict[str, Any]] = []
    periods: set[dt.date] = set()
    for period, record in eligible:
        if period in periods:
            continue
        periods.add(period)
        selected.append(record)
        if len(selected) >= period_limit:
            break
    return selected


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            row["security_code"],
            -int(row["period"].replace("-", "")),
            CORE_ORDER.get(row["normalized_line_item"], len(CORE_ORDER)),
            "" if row["normalized_line_item"] in CORE_ORDER else row["source_line_item"],
            row["statement_item_id"],
        ),
    )


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(output_dir: Path, as_of: str, period_limit: int) -> None:
    path = output_dir / "source_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"files": []}
    files = payload.setdefault("files", [])
    files[:] = [item for item in files if item.get("file") != "financial_statements.csv"]
    files.append(
        {
            "file": "financial_statements.csv",
            "source_type": "public_market_data",
            "source_name": SOURCE_NAME,
            "data_time": as_of[:10],
            "period_or_basis": (
                f"资产负债表；截至 {as_of[:10]} 每证券最多 {period_limit} 个报告期；"
                "报告期末时点值；金额为人民币元；规范核心科目保留明确来源字段；"
                "statement_scope 为来源缺失"
            ),
            "verification_status": "verified",
            "missing_behavior": (
                "无数据写 financial_statement_balance_sheet_no_data；输入或请求失败写对应 "
                "financial_statement 阶段；来源未声明报表范围时为来源缺失，不得据此执行跨公司比较"
            ),
        }
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_errors(output_dir: Path, errors: list[dict[str, str]]) -> None:
    path = output_dir / "fetch_errors.csv"
    existing: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = [
                row for row in csv.DictReader(handle)
                if not row.get("stage", "").startswith("financial_statement")
            ]
    write_csv(path, existing + errors, ERROR_COLUMNS)


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    errors: list[dict[str, str]],
    as_of: str,
    period_limit: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "financial_statements.csv", sort_rows(rows), STATEMENT_COLUMNS)
    write_manifest(output_dir, as_of, period_limit)
    write_errors(output_dir, errors)


def run_pipeline(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    try:
        if args.period_limit < 1:
            raise ValueError("--period-limit must be positive")
        as_of = dt.date.fromisoformat(args.as_of[:10])
        peers, input_errors = read_peers(Path(args.peer_universe))
        errors.extend(input_errors)
    except Exception as exc:
        errors.append(error_row(MISSING, "financial_statement_input", str(exc)))
        write_outputs(output_dir, [], errors, args.as_of, args.period_limit)
        print(f"financial statement input failed: {exc}", file=sys.stderr)
        return 1

    for sequence, peer in enumerate(peers, start=1):
        try:
            records = (
                fixture_records(peer, args.fixture_scenario, sequence)
                if args.source == "fixture"
                else fetch_akshare_records(peer["code"])
            )
            selected = select_records(records, as_of, args.period_limit)
            if not selected:
                errors.append(
                    error_row(
                        peer["code"],
                        "financial_statement_balance_sheet_no_data",
                        f"截至 {as_of.isoformat()} 未返回可用资产负债表",
                    )
                )
                continue
            for record in selected:
                rows.extend(normalize_record(record, peer))
        except Exception as exc:
            errors.append(error_row(peer["code"], "financial_statement_balance_sheet", str(exc)))

    write_outputs(output_dir, rows, errors, args.as_of, args.period_limit)
    print(f"wrote balance-sheet financial statements: {output_dir}")
    if errors:
        print(f"completed with {len(errors)} financial statement notice(s)", file=sys.stderr)
    return 0


def main() -> int:
    return run_pipeline(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
