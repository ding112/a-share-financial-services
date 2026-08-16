#!/usr/bin/env python3
"""离线验证 A 股财务报表明细公开 CLI 契约。"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FETCHER = ROOT / "scripts/fetch_a_share_financial_statements.py"

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
BALANCE_SHEET_CORE_ORDER = [
    "monetary_funds",
    "accounts_receivable",
    "inventory",
    "contract_assets",
    "fixed_assets",
    "construction_in_progress",
    "intangible_assets",
    "goodwill",
    "current_assets",
    "total_assets",
    "accounts_payable",
    "contract_liabilities",
    "short_term_borrowings",
    "long_term_borrowings",
    "bonds_payable",
    "lease_liabilities",
    "current_liabilities",
    "total_liabilities",
    "equity_attributable_to_parent",
    "minority_interests",
    "total_equity",
]
INCOME_STATEMENT_CORE_ORDER = [
    "revenue",
    "cost_of_revenue",
    "selling_expenses",
    "administrative_expenses",
    "research_and_development_expenses",
    "financial_expenses",
    "operating_profit",
    "total_profit",
    "income_tax_expense",
    "net_profit",
    "net_profit_attributable_to_parent",
    "minority_profit",
    "basic_eps",
    "diluted_eps",
]
CORE_ORDER = {
    "balance_sheet": BALANCE_SHEET_CORE_ORDER,
    "income_statement": INCOME_STATEMENT_CORE_ORDER,
}
STATEMENT_TYPE_ORDER = {"balance_sheet": 0, "income_statement": 1}


def write_peers(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name"])
        writer.writeheader()
        writer.writerows(
            [
                {"code": "600519.SH", "name": "贵州茅台"},
                {"code": "002594.SZ", "name": "比亚迪"},
            ]
        )


def write_invalid_peers(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name"])
        writer.writeheader()
        writer.writerow({"code": "not-a-security", "name": "坏样本"})


def write_single_peer(path: Path, code: str, name: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name"])
        writer.writeheader()
        writer.writerow({"code": code, "name": name})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_fetcher(root: Path, peers: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(FETCHER),
            "--peer-universe",
            str(peers),
            "--output-dir",
            str(root / "output"),
            "--as-of",
            "2026-08-16",
            "--period-limit",
            "2",
            "--source",
            "fixture",
            "--fixture-scenario",
            "success",
            *extra,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def stable_id(row: dict[str, str]) -> str:
    material = "\x1f".join(
        [
            row["security_code"],
            row["statement_type"],
            row["period"],
            row["source_line_item"],
        ]
    )
    return "fs_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def expected_sort_key(row: dict[str, str]) -> tuple[object, ...]:
    normalized = row["normalized_line_item"]
    core_order = CORE_ORDER[row["statement_type"]]
    core_index = core_order.index(normalized) if normalized in core_order else len(core_order)
    return (
        row["security_code"],
        -int(row["period"].replace("-", "")),
        STATEMENT_TYPE_ORDER[row["statement_type"]],
        core_index,
        "" if normalized in core_order else row["source_line_item"],
        row["statement_item_id"],
    )


def validate_success(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        write_peers(peers)
        result = run_fetcher(root, peers)
        if result.returncode != 0:
            errors.append(f"成功场景退出码为 {result.returncode}: {result.stderr}")
            return

        output = root / "output"
        statements_path = output / "financial_statements.csv"
        if not statements_path.is_file():
            errors.append("成功场景缺少 financial_statements.csv")
            return
        with statements_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != STATEMENT_COLUMNS:
                errors.append(f"财务报表明细列不符合契约: {reader.fieldnames}")
            rows = list(reader)

        if not rows:
            errors.append("成功场景未输出财务报表明细")
            return
        if {row["security_code"] for row in rows} != {"600519.SH", "002594.SZ"}:
            errors.append("成功场景必须同时覆盖沪深证券")
        if {row["statement_type"] for row in rows} != {"balance_sheet", "income_statement"}:
            errors.append("成功场景必须同时输出资产负债表和利润表明细")
        if any(
            row["value_semantics"] != {"balance_sheet": "point_in_time", "income_statement": "year_to_date"}[row["statement_type"]]
            for row in rows
        ):
            errors.append("两类报表必须使用各自固定的期间语义")
        if any(row["statement_scope"] != "来源缺失" for row in rows):
            errors.append("来源未声明范围时 statement_scope 必须为来源缺失")
        if any(
            row["source_type"] != "public_market_data"
            or row["source_name"] != "AkShare（东方财富财务报表）"
            for row in rows
        ):
            errors.append("财务报表行来源元数据不符合契约")
        if any(
            row["statement_item_id"] != stable_id(row)
            or not row["statement_item_id"].startswith("fs_")
            or len(row["statement_item_id"]) != 27
            for row in rows
        ):
            errors.append("财务报表行稳定 ID 不符合身份键契约")
        if rows != sorted(rows, key=expected_sort_key):
            errors.append("财务报表行排序不符合证券、期间、报表类型、核心科目和来源字段契约")
        if any(row["source_line_item"].endswith("_YOY") for row in rows):
            errors.append("同比字段不应生成资产负债表行项目")
        if any(row["source_line_item"] in {"REPORT_DATE", "ORG_TYPE", "OPINION_TYPE"} for row in rows):
            errors.append("报表元数据不应生成资产负债表行项目")

        latest_rows = [row for row in rows if row["period"] == "2025-12-31"]
        latest_core = {
            row["normalized_line_item"]
            for row in latest_rows
            if row["security_code"] == "600519.SH"
        }
        if not set(BALANCE_SHEET_CORE_ORDER).issubset(latest_core):
            errors.append("沪市成功样本未覆盖全部资产负债表核心科目")
        mapping_conflict = [
            row
            for row in latest_rows
            if row["security_code"] == "600519.SH"
            and row["source_line_item"] == "PARENT_EQUITY_BALANCE"
        ]
        if len(mapping_conflict) != 1 or mapping_conflict[0]["normalized_line_item"] != "来源缺失":
            errors.append("映射冲突中的低优先级原始行必须保留且不得获得规范名称")
        parent_equity = [
            row
            for row in latest_rows
            if row["security_code"] == "600519.SH"
            and row["source_line_item"] == "TOTAL_PARENT_EQUITY"
        ]
        if len(parent_equity) != 1 or parent_equity[0]["normalized_line_item"] != "equity_attributable_to_parent":
            errors.append("映射冲突中的最高优先级行必须获得 equity_attributable_to_parent")
        goodwill_placeholder = [
            row
            for row in latest_rows
            if row["security_code"] == "002594.SZ"
            and row["normalized_line_item"] == "goodwill"
        ]
        if len(goodwill_placeholder) != 1 or goodwill_placeholder[0]["source_line_item"] != "core:goodwill":
            errors.append("缺失核心科目必须生成唯一 core:goodwill 占位行")
        elif any(goodwill_placeholder[0][field] != "来源缺失" for field in ["value", "unit", "verification_status"]):
            errors.append("核心占位行必须以来源缺失表达值、单位和验证状态")
        known_money_rows = [row for row in rows if row["source_line_item"] == "MONETARYFUNDS"]
        if not known_money_rows or any(row["unit"] != "CNY" or row["verification_status"] != "verified" for row in known_money_rows):
            errors.append("已知货币资金必须使用 CNY 和 verified")
        if any(row["organization_type"] == "" or row["currency"] == "" for row in rows):
            errors.append("成功场景必须保留组织类型和币种元数据")

        latest_income_rows = [
            row for row in rows
            if row["period"] == "2025-12-31" and row["statement_type"] == "income_statement"
        ]
        latest_income_core = {
            row["normalized_line_item"]
            for row in latest_income_rows
            if row["security_code"] == "600519.SH"
        }
        if not set(INCOME_STATEMENT_CORE_ORDER).issubset(latest_income_core):
            errors.append("沪市成功样本未覆盖全部利润表核心科目")
        revenue_conflict = [
            row for row in latest_income_rows
            if row["security_code"] == "600519.SH" and row["source_line_item"] == "OPERATE_INCOME"
        ]
        if len(revenue_conflict) != 1 or revenue_conflict[0]["normalized_line_item"] != "来源缺失":
            errors.append("利润表收入映射冲突中的低优先级原始行必须保留且不得获得规范名称")
        revenue = [
            row for row in latest_income_rows
            if row["security_code"] == "600519.SH" and row["source_line_item"] == "TOTAL_OPERATE_INCOME"
        ]
        if len(revenue) != 1 or revenue[0]["normalized_line_item"] != "revenue":
            errors.append("利润表收入映射必须优先使用 TOTAL_OPERATE_INCOME")
        diluted_eps_placeholder = [
            row for row in latest_income_rows
            if row["security_code"] == "002594.SZ" and row["normalized_line_item"] == "diluted_eps"
        ]
        if len(diluted_eps_placeholder) != 1 or diluted_eps_placeholder[0]["source_line_item"] != "core:diluted_eps":
            errors.append("利润表缺失核心科目必须生成唯一 core:diluted_eps 占位行")
        eps_rows = [row for row in rows if row["source_line_item"] in {"BASIC_EPS", "DILUTED_EPS"}]
        if not eps_rows or any(row["unit"] != "CNY/share" or row["verification_status"] != "verified" for row in eps_rows):
            errors.append("基本和稀释 EPS 必须使用 CNY/share 和 verified")
        if any(row["source_line_item"].endswith("_YOY") for row in latest_income_rows):
            errors.append("同比字段不应生成利润表行项目")
        income_audit_rows = [row for row in latest_income_rows if row["security_code"] == "600519.SH"]
        if any(row["domestic_audit_opinion"] != "标准无保留意见" for row in income_audit_rows):
            errors.append("利润表必须保留来源国内审计意见")
        if any(row["overseas_audit_opinion"] != "来源缺失" for row in income_audit_rows):
            errors.append("利润表未提供海外审计意见时必须写来源缺失")

        manifest_path = output / "source_manifest.json"
        errors_path = output / "fetch_errors.csv"
        if not manifest_path.is_file() or not errors_path.is_file():
            errors.append("成功场景缺少来源清单或统一错误文件")
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = [
            item for item in manifest.get("files", [])
            if item.get("file") == "financial_statements.csv"
        ]
        if len(entries) != 1:
            errors.append("来源清单必须只包含一条财务报表明细条目")
        elif any(token not in str(entries[0]) for token in ["资产负债表", "利润表", "2", "时点", "累计", "来源缺失"]):
            errors.append("来源清单缺少两类报表、期间数量、时点/累计语义或范围边界")
        if read_rows(errors_path):
            errors.append("成功场景不应产生抓取错误")

        first_bytes = statements_path.read_bytes()
        second = run_fetcher(root, peers)
        if second.returncode != 0 or statements_path.read_bytes() != first_bytes:
            errors.append("相同 fixture 重跑必须生成字节稳定的财务报表 CSV")


def validate_input_errors(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "invalid.csv"
        write_invalid_peers(peers)
        result = run_fetcher(root, peers)
        output = root / "output"
        if result.returncode == 0:
            errors.append("没有有效证券的股票池必须返回非零")
        statements = output / "financial_statements.csv"
        notices = output / "fetch_errors.csv"
        if not statements.is_file() or not notices.is_file():
            errors.append("致命输入错误仍必须写稳定 CSV 和错误文件")
            return
        with statements.open(newline="", encoding="utf-8") as handle:
            if csv.DictReader(handle).fieldnames != STATEMENT_COLUMNS:
                errors.append("致命输入错误的 CSV 表头不稳定")
        stages = {row.get("stage") for row in read_rows(notices)}
        if "financial_statement_input" not in stages:
            errors.append("致命输入错误必须记录 financial_statement_input")

        invalid_period = run_fetcher(root, peers, "--period-limit", "not-a-number")
        if invalid_period.returncode == 0:
            errors.append("无法解析的 --period-limit 必须返回非零")
        if not statements.is_file() or not notices.is_file():
            errors.append("无法解析的 --period-limit 仍必须写稳定产物")
        elif "financial_statement_input" not in {row.get("stage") for row in read_rows(notices)}:
            errors.append("无法解析的 --period-limit 必须记录 financial_statement_input")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output = root / "output"
        result = subprocess.run(
            [
                sys.executable,
                str(FETCHER),
                "--output-dir",
                str(output),
                "--as-of",
                "2026-08-16",
                "--source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            errors.append("缺少 --peer-universe 必须返回非零")
        if not (output / "financial_statements.csv").is_file() or not (output / "fetch_errors.csv").is_file():
            errors.append("缺少 --peer-universe 仍必须写稳定产物")


def validate_unknown_field(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        write_peers(peers)
        result = run_fetcher(root, peers, "--fixture-scenario", "unknown-field")
        if result.returncode != 0:
            errors.append(f"未知字段场景退出码为 {result.returncode}: {result.stderr}")
            return
        rows = read_rows(root / "output" / "financial_statements.csv")
        unknown = [row for row in rows if row["source_line_item"] == "FUTURE_ASSET_ITEM"]
        if len(unknown) != 2:
            errors.append("非空未知来源字段必须为每个证券保留原始行")
        elif any(
            row["normalized_line_item"] != "来源缺失"
            or row["unit"] != "来源缺失"
            or row["verification_status"] != "待验证"
            for row in unknown
        ):
            errors.append("未知来源字段必须使用来源缺失单位/规范名与待验证状态")
        stages = {row.get("stage") for row in read_rows(root / "output" / "fetch_errors.csv")}
        if "financial_statement_schema" not in stages:
            errors.append("未知来源字段必须记录 financial_statement_schema")


def validate_income_statement_degradations(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        write_peers(peers)
        result = run_fetcher(root, peers, "--fixture-scenario", "non-annual")
        if result.returncode != 0:
            errors.append(f"非年报场景退出码为 {result.returncode}: {result.stderr}")
            return
        income_rows = [
            row for row in read_rows(root / "output" / "financial_statements.csv")
            if row["statement_type"] == "income_statement"
        ]
        if not income_rows or any(
            row["domestic_audit_opinion"] != "来源缺失"
            or row["overseas_audit_opinion"] != "来源缺失"
            for row in income_rows
        ):
            errors.append("非年报利润表的国内和海外审计意见必须降级为来源缺失")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        write_peers(peers)
        result = run_fetcher(root, peers, "--fixture-scenario", "invalid-income-value")
        if result.returncode != 0:
            errors.append(f"利润表异常数值场景退出码为 {result.returncode}: {result.stderr}")
            return
        rows = read_rows(root / "output" / "financial_statements.csv")
        invalid_rows = [
            row for row in rows
            if row["statement_type"] == "income_statement"
            and row["source_line_item"] == "BASIC_EPS"
            and row["value"] == "not-a-number"
        ]
        if not invalid_rows or any(
            row["unit"] != "CNY/share"
            or row["normalized_line_item"] != "来源缺失"
            or row["verification_status"] != "待验证"
            for row in invalid_rows
        ):
            errors.append("无法解析的已知利润表项目必须保留原值并明确降级")
        stages = {row.get("stage") for row in read_rows(root / "output" / "fetch_errors.csv")}
        if "financial_statement_schema" not in stages:
            errors.append("无法解析的已知利润表项目必须记录 financial_statement_schema")


def validate_bj_unsupported(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        write_single_peer(peers, "920001.BJ", "北交所样本")
        result = run_fetcher(root, peers)
        if result.returncode != 0:
            errors.append("北交所不支持应作为降级而非命令失败")
        rows = read_rows(root / "output" / "financial_statements.csv")
        if rows:
            errors.append("北交所不支持时不得输出伪资产负债表明细")
        stages = {row.get("stage") for row in read_rows(root / "output" / "fetch_errors.csv")}
        if "financial_statement_unsupported" not in stages:
            errors.append("北交所不支持必须记录 financial_statement_unsupported")


def main() -> int:
    errors: list[str] = []
    validate_success(errors)
    validate_input_errors(errors)
    validate_unknown_field(errors)
    validate_income_statement_degradations(errors)
    validate_bj_unsupported(errors)
    if errors:
        print(f"FAIL — {len(errors)} A 股财务报表明细问题:", file=sys.stderr)
        for error in errors:
            print(f"  ✗ {error}", file=sys.stderr)
        return 1
    print("OK — A 股资产负债表和利润表明细 CLI 契约已验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
