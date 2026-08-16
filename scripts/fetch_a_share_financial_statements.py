#!/usr/bin/env python3
"""为 A 股 research-pack 抓取资产负债表和利润表明细。

保留来源的非空行项目，并只为口径明确的核心项目提供规范名称；不把当前
来源未声明的报表范围猜测为合并或母公司口径。
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

BALANCE_SHEET_CORE_MAPPINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
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
INCOME_STATEMENT_CORE_MAPPINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("revenue", ("TOTAL_OPERATE_INCOME", "OPERATE_INCOME")),
    ("cost_of_revenue", ("OPERATE_COST",)),
    ("selling_expenses", ("SALE_EXPENSE",)),
    ("administrative_expenses", ("MANAGE_EXPENSE",)),
    ("research_and_development_expenses", ("RESEARCH_EXPENSE", "ME_RESEARCH_EXPENSE")),
    ("financial_expenses", ("FINANCE_EXPENSE",)),
    ("operating_profit", ("OPERATE_PROFIT",)),
    ("total_profit", ("TOTAL_PROFIT",)),
    ("income_tax_expense", ("INCOME_TAX",)),
    ("net_profit", ("NETPROFIT",)),
    ("net_profit_attributable_to_parent", ("PARENT_NETPROFIT",)),
    ("minority_profit", ("MINORITY_INTEREST",)),
    ("basic_eps", ("BASIC_EPS",)),
    ("diluted_eps", ("DILUTED_EPS",)),
)
CORE_MAPPINGS = {
    "balance_sheet": BALANCE_SHEET_CORE_MAPPINGS,
    "income_statement": INCOME_STATEMENT_CORE_MAPPINGS,
}
CORE_ORDER = {
    statement_type: {name: index for index, (name, _) in enumerate(mappings)}
    for statement_type, mappings in CORE_MAPPINGS.items()
}
STATEMENT_TYPE_ORDER = {"balance_sheet": 0, "income_statement": 1}
STATEMENT_LABELS = {"balance_sheet": "资产负债表", "income_statement": "利润表"}
VALUE_SEMANTICS = {"balance_sheet": "point_in_time", "income_statement": "year_to_date"}

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

# 当前 AkShare 利润表接口公开的金额和每股字段目录。同比字段明确排除，
# 以免把增长率混入来源披露的期间累计金额。
KNOWN_INCOME_STATEMENT_FIELDS = frozenset(
    """
    TOTAL_OPERATE_INCOME OPERATE_INCOME INTEREST_INCOME EARNED_PREMIUM
    FEE_COMMISSION_INCOME OTHER_BUSINESS_INCOME TOI_OTHER TOTAL_OPERATE_COST
    OPERATE_COST INTEREST_EXPENSE FEE_COMMISSION_EXPENSE RESEARCH_EXPENSE
    SURRENDER_VALUE NET_COMPENSATE_EXPENSE NET_CONTRACT_RESERVE
    POLICY_BONUS_EXPENSE REINSURE_EXPENSE OTHER_BUSINESS_COST OPERATE_TAX_ADD
    SALE_EXPENSE MANAGE_EXPENSE ME_RESEARCH_EXPENSE FINANCE_EXPENSE
    FE_INTEREST_EXPENSE FE_INTEREST_INCOME ASSET_IMPAIRMENT_LOSS
    CREDIT_IMPAIRMENT_LOSS TOC_OTHER FAIRVALUE_CHANGE_INCOME INVEST_INCOME
    INVEST_JOINT_INCOME NET_EXPOSURE_INCOME EXCHANGE_INCOME
    ASSET_DISPOSAL_INCOME ASSET_IMPAIRMENT_INCOME CREDIT_IMPAIRMENT_INCOME
    OTHER_INCOME OPERATE_PROFIT_OTHER OPERATE_PROFIT_BALANCE OPERATE_PROFIT
    NONBUSINESS_INCOME NONCURRENT_DISPOSAL_INCOME NONBUSINESS_EXPENSE
    NONCURRENT_DISPOSAL_LOSS EFFECT_TP_OTHER TOTAL_PROFIT_BALANCE TOTAL_PROFIT
    INCOME_TAX EFFECT_NETPROFIT_OTHER EFFECT_NETPROFIT_BALANCE
    UNCONFIRM_INVEST_LOSS NETPROFIT PRECOMBINE_PROFIT CONTINUED_NETPROFIT
    DISCONTINUED_NETPROFIT PARENT_NETPROFIT MINORITY_INTEREST
    DEDUCT_PARENT_NETPROFIT NETPROFIT_OTHER NETPROFIT_BALANCE BASIC_EPS
    DILUTED_EPS OTHER_COMPRE_INCOME PARENT_OCI MINORITY_OCI PARENT_OCI_OTHER
    PARENT_OCI_BALANCE UNABLE_OCI CREDITRISK_FAIRVALUE_CHANGE
    OTHERRIGHT_FAIRVALUE_CHANGE SETUP_PROFIT_CHANGE RIGHTLAW_UNABLE_OCI
    UNABLE_OCI_OTHER UNABLE_OCI_BALANCE ABLE_OCI RIGHTLAW_ABLE_OCI
    AFA_FAIRVALUE_CHANGE HMI_AFA CASHFLOW_HEDGE_VALID CREDITOR_FAIRVALUE_CHANGE
    CREDITOR_IMPAIRMENT_RESERVE FINANCE_OCI_AMT CONVERT_DIFF ABLE_OCI_OTHER
    ABLE_OCI_BALANCE OCI_OTHER OCI_BALANCE TOTAL_COMPRE_INCOME PARENT_TCI
    MINORITY_TCI PRECOMBINE_TCI EFFECT_TCI_BALANCE TCI_OTHER TCI_BALANCE
    ACF_END_INCOME
    """.split()
)
PER_SHARE_FIELDS = frozenset({"BASIC_EPS", "DILUTED_EPS"})
KNOWN_FIELDS = {
    "balance_sheet": KNOWN_AMOUNT_FIELDS,
    "income_statement": KNOWN_INCOME_STATEMENT_FIELDS,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", help="包含 A 股股票池的 CSV。")
    parser.add_argument("--output-dir", required=True, help="research-pack 输出目录。")
    parser.add_argument("--as-of", required=True, help="研究截止日，例如 2026-08-16。")
    parser.add_argument(
        "--period-limit",
        default="12",
        help="每个证券每张报表最多保留的报告期数，默认 12。",
    )
    parser.add_argument(
        "--source",
        choices=["akshare", "fixture"],
        default="akshare",
        help="财务报表来源；fixture 仅用于离线检查。",
    )
    parser.add_argument(
        "--fixture-scenario",
        choices=["success", "no-data", "unknown-field", "non-annual", "invalid-income-value"],
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
        raise ValueError(f"不支持的 A 股代码: {raw_code!r}")
    symbol = match.group(1).zfill(6)
    inferred = infer_exchange(symbol)
    supplied = match.group(2)
    if inferred is None or (supplied and supplied != inferred):
        raise ValueError(f"不支持的 A 股代码: {raw_code!r}")
    return f"{symbol}.{inferred}"


def error_row(code: str, stage: str, error: str) -> dict[str, str]:
    return {"code": code, "source": SOURCE_KEY, "stage": stage, "error": error}


def read_peers(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "code" not in reader.fieldnames:
            raise ValueError(f"股票池需要 code 列: {path}")
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
        raise ValueError(f"股票池不包含有效 A 股代码: {path}")
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
        raise ValueError("数值为空")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"无法解析数值: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"无法解析数值: {value!r}")
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
        raise ValueError(f"财务报表缺少 {field}")
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"财务报表 {field} 无法解析: {value!r}") from exc


def date_text(value: Any, field: str) -> str:
    return parse_date(value, field).isoformat()


def statement_item_id(code: str, statement_type: str, period: str, source_line_item: str) -> str:
    material = "\x1f".join((code, statement_type, period, source_line_item))
    return "fs_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def core_mapping_for_field(statement_type: str, field: str) -> str | None:
    for normalized, candidates in CORE_MAPPINGS[statement_type]:
        if field in candidates:
            return normalized
    return None


def selected_core_fields(statement_type: str, record: dict[str, Any]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for normalized, candidates in CORE_MAPPINGS[statement_type]:
        for field in candidates:
            if field in record and not is_missing(record[field]):
                try:
                    decimal_text(record[field])
                except ValueError:
                    continue
                selected[normalized] = field
                break
    return selected


def item_basis(statement_type: str, field: str, normalized: str, unit: str) -> str:
    mapping = normalized if normalized != MISSING else "未映射来源项目"
    return (
        f"{STATEMENT_LABELS[statement_type]}来源字段 {field}；规范项目 {mapping}；单位 {unit}；"
        f"{VALUE_SEMANTICS[statement_type]}；报表范围来源缺失"
    )


def metadata_from_record(
    statement_type: str, record: dict[str, Any], peer: dict[str, str]
) -> dict[str, str]:
    period = date_text(record.get("REPORT_DATE"), "REPORT_DATE")
    report_type = str(record.get("REPORT_TYPE") or MISSING)
    audit_opinion_available = report_type == "年报"
    return {
        "security_code": peer["code"],
        "security_name": str(record.get("SECURITY_NAME_ABBR") or peer["name"] or MISSING),
        "organization_type": str(record.get("ORG_TYPE") or MISSING),
        "statement_type": statement_type,
        "period": period,
        "report_type": report_type,
        "notice_date": date_text(record.get("NOTICE_DATE"), "NOTICE_DATE"),
        "update_date": date_text(record.get("UPDATE_DATE"), "UPDATE_DATE"),
        "currency": str(record.get("CURRENCY") or MISSING),
        "statement_scope": MISSING,
        "value_semantics": VALUE_SEMANTICS[statement_type],
        "domestic_audit_opinion": (
            str(record.get("OPINION_TYPE") or MISSING) if audit_opinion_available else MISSING
        ),
        "overseas_audit_opinion": (
            str(record.get("OSOPINION_TYPE") or MISSING) if audit_opinion_available else MISSING
        ),
        "source_type": "public_market_data",
        "source_name": SOURCE_NAME,
    }


def raw_item_rows(
    statement_type: str, record: dict[str, Any], metadata: dict[str, str]
) -> tuple[list[dict[str, str]], list[str]]:
    selected = selected_core_fields(statement_type, record)
    rows: list[dict[str, str]] = []
    schema_messages: list[str] = []
    for field in sorted(record):
        value = record[field]
        if field in METADATA_FIELDS or field.endswith("_YOY") or is_missing(value):
            continue
        known_amount = field in KNOWN_FIELDS[statement_type]
        if known_amount:
            try:
                value_text = decimal_text(value)
            except ValueError:
                value_text = str(value).strip()
                unit = "CNY/share" if field in PER_SHARE_FIELDS else "CNY"
                verification_status = "待验证"
                schema_messages.append(f"{STATEMENT_LABELS[statement_type]}字段无法解析为数值: {field}")
            else:
                unit = "CNY/share" if field in PER_SHARE_FIELDS else "CNY"
                verification_status = "verified"
        else:
            value_text = str(value).strip()
            unit = MISSING
            verification_status = "待验证"
            schema_messages.append(f"{STATEMENT_LABELS[statement_type]}出现未识别行项目: {field}")
        normalized = core_mapping_for_field(statement_type, field) or MISSING
        if normalized != MISSING and selected.get(normalized) != field:
            normalized = MISSING
        row = dict(metadata)
        row.update(
            {
                "source_line_item": field,
                "normalized_line_item": normalized,
                "value": value_text,
                "unit": unit,
                "verification_status": verification_status,
                "basis": item_basis(statement_type, field, normalized, unit),
            }
        )
        row["statement_item_id"] = statement_item_id(
            row["security_code"], row["statement_type"], row["period"], field
        )
        rows.append(row)
    return rows, schema_messages


def missing_core_rows(
    statement_type: str, rows: list[dict[str, str]], metadata: dict[str, str]
) -> list[dict[str, str]]:
    present = {row["normalized_line_item"] for row in rows if row["normalized_line_item"] != MISSING}
    placeholders: list[dict[str, str]] = []
    for normalized, _ in CORE_MAPPINGS[statement_type]:
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
                "basis": f"该{STATEMENT_LABELS[statement_type]}记录中未找到适用来源项目；报表范围来源缺失",
            }
        )
        row["statement_item_id"] = statement_item_id(
            row["security_code"], row["statement_type"], row["period"], source_line_item
        )
        placeholders.append(row)
    return placeholders


def normalize_record(
    statement_type: str, record: dict[str, Any], peer: dict[str, str]
) -> tuple[list[dict[str, str]], list[str]]:
    metadata = metadata_from_record(statement_type, record, peer)
    rows, schema_messages = raw_item_rows(statement_type, record, metadata)
    return rows + missing_core_rows(statement_type, rows, metadata), schema_messages


def fixture_metadata(peer: dict[str, str], period: str, sequence: int) -> dict[str, Any]:
    return {
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
        "OSOPINION_TYPE": MISSING,
        "LISTING_STATE": "0",
    }


def balance_sheet_fixture_record(peer: dict[str, str], period: str, sequence: int) -> dict[str, Any]:
    amount = 1000 + sequence * 100
    record = fixture_metadata(peer, period, sequence)
    record.update({
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
    })
    if peer["code"] == "600519.SH" and period == "2025-12-31":
        record["PARENT_EQUITY_BALANCE"] = amount + 119
    if peer["code"] == "002594.SZ" and period == "2025-12-31":
        record.pop("GOODWILL")
    return record


def income_statement_fixture_record(peer: dict[str, str], period: str, sequence: int) -> dict[str, Any]:
    amount = 2000 + sequence * 100
    record = fixture_metadata(peer, period, sequence)
    record.update(
        {
            "TOTAL_OPERATE_INCOME": amount + 1,
            "OPERATE_INCOME": amount + 2,
            "OPERATE_COST": amount + 3,
            "SALE_EXPENSE": amount + 4,
            "MANAGE_EXPENSE": amount + 5,
            "RESEARCH_EXPENSE": amount + 6,
            "FINANCE_EXPENSE": amount + 7,
            "OPERATE_PROFIT": amount + 8,
            "TOTAL_PROFIT": amount + 9,
            "INCOME_TAX": amount + 10,
            "NETPROFIT": amount + 11,
            "PARENT_NETPROFIT": amount + 12,
            "MINORITY_INTEREST": amount + 13,
            "BASIC_EPS": "1.23",
            "DILUTED_EPS": "1.20",
            "TOTAL_OPERATE_INCOME_YOY": "8.2",
        }
    )
    if peer["code"] == "002594.SZ" and period == "2025-12-31":
        record.pop("DILUTED_EPS")
    return record


def fixture_records(
    statement_type: str, peer: dict[str, str], scenario: str, sequence: int
) -> list[dict[str, Any]]:
    if scenario == "no-data":
        return []
    records = [
        (
            balance_sheet_fixture_record(peer, "2025-12-31", sequence)
            if statement_type == "balance_sheet"
            else income_statement_fixture_record(peer, "2025-12-31", sequence)
        ),
        (
            balance_sheet_fixture_record(peer, "2024-12-31", sequence)
            if statement_type == "balance_sheet"
            else income_statement_fixture_record(peer, "2024-12-31", sequence)
        ),
    ]
    if scenario == "unknown-field" and statement_type == "balance_sheet":
        records[0]["FUTURE_ASSET_ITEM"] = 9876
    if scenario == "non-annual":
        for record in records:
            record["REPORT_TYPE"] = "中报"
    if scenario == "invalid-income-value" and statement_type == "income_statement":
        records[0]["BASIC_EPS"] = "not-a-number"
    return records


def fetch_akshare_records(statement_type: str, code: str) -> list[dict[str, Any]]:
    import akshare as ak  # type: ignore[import-not-found]

    symbol, exchange = code.split(".", 1)
    if statement_type == "balance_sheet":
        frame = ak.stock_balance_sheet_by_report_em(symbol=f"{exchange}{symbol}")
    else:
        frame = ak.stock_profit_sheet_by_report_em(symbol=f"{exchange}{symbol}")
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
            STATEMENT_TYPE_ORDER[row["statement_type"]],
            CORE_ORDER[row["statement_type"]].get(
                row["normalized_line_item"], len(CORE_ORDER[row["statement_type"]])
            ),
            ""
            if row["normalized_line_item"] in CORE_ORDER[row["statement_type"]]
            else row["source_line_item"],
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
                f"资产负债表和利润表；截至 {as_of[:10]} 每证券每表最多 {period_limit} 个报告期；"
                "资产负债表为报告期末时点值，利润表为年初至报告期末累计值；"
                "金额为人民币元、每股收益为人民币元/股；规范核心科目保留明确来源字段；"
                "statement_scope 为来源缺失"
            ),
            "verification_status": "verified",
            "missing_behavior": (
                "无数据写对应 financial_statement_*_no_data；输入或请求失败写对应 "
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
        try:
            period_limit = int(args.period_limit)
        except ValueError as exc:
            raise ValueError("--period-limit 必须为正整数") from exc
        if period_limit < 1:
            raise ValueError("--period-limit 必须为正整数")
        as_of = dt.date.fromisoformat(args.as_of[:10])
        if not args.peer_universe:
            raise ValueError("缺少 --peer-universe")
        peers, input_errors = read_peers(Path(args.peer_universe))
        errors.extend(input_errors)
    except Exception as exc:
        errors.append(error_row(MISSING, "financial_statement_input", str(exc)))
        write_outputs(output_dir, [], errors, args.as_of, 12)
        print(f"财务报表明细输入失败: {exc}", file=sys.stderr)
        return 1

    for sequence, peer in enumerate(peers, start=1):
        if peer["code"].endswith(".BJ"):
            errors.append(
                error_row(
                    peer["code"],
                    "financial_statement_unsupported",
                    "第一版财务报表明细仅支持上交所和深交所证券",
                )
            )
            continue
        for statement_type in ("balance_sheet", "income_statement"):
            label = STATEMENT_LABELS[statement_type]
            try:
                records = (
                    fixture_records(statement_type, peer, args.fixture_scenario, sequence)
                    if args.source == "fixture"
                    else fetch_akshare_records(statement_type, peer["code"])
                )
                selected = select_records(records, as_of, period_limit)
                if not selected:
                    errors.append(
                        error_row(
                            peer["code"],
                            f"financial_statement_{statement_type}_no_data",
                            f"截至 {as_of.isoformat()} 未返回可用{label}",
                        )
                    )
                    continue
                for record in selected:
                    normalized_rows, schema_messages = normalize_record(statement_type, record, peer)
                    rows.extend(normalized_rows)
                    errors.extend(
                        error_row(peer["code"], "financial_statement_schema", message)
                        for message in schema_messages
                    )
            except Exception as exc:
                errors.append(error_row(peer["code"], f"financial_statement_{statement_type}", str(exc)))

    write_outputs(output_dir, rows, errors, args.as_of, period_limit)
    print(f"已写入资产负债表和利润表明细: {output_dir}")
    if errors:
        print(f"财务报表明细完成，含 {len(errors)} 条提示", file=sys.stderr)
    return 0


def main() -> int:
    return run_pipeline(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
