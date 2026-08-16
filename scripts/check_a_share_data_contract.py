#!/usr/bin/env python3
"""Validate the A-share data source contract skill."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md"
BUNDLED = ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md"
COMPS_SOURCE = ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md"
COMPS_BUNDLED = ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md"
QUICK_START = ROOT / "docs/quick-start.md"
ROADMAP = ROOT / "docs/china-equity-trading-roadmap.md"
MANAGED_README = ROOT / "managed-agent-cookbooks/a-share-market-researcher/README.md"
AGENT_PROMPT = ROOT / "plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md"
DATA_PREP_AGENT = ROOT / "managed-agent-cookbooks/a-share-market-researcher/subagents/data-prep.yaml"

REQUIRED_SECTIONS = [
    "## 研究事实类型",
    "## 来源等级契约",
    "## 研究数据包契约",
    "## 字段来源契约",
    "## 引用元数据 schema",
    "## 降级规则",
    "## 下游技能最低证据门槛",
]

REQUIRED_SOURCE_TYPES = [
    "official_disclosure",
    "official_statistics",
    "public_market_data",
    "company_public_material",
    "third_party",
    "user_provided",
    "missing_source",
]

REQUIRED_METADATA_FIELDS = [
    "字段名",
    "事实或数值",
    "来源类型",
    "来源名称",
    "数据时间",
    "报告期或口径",
    "验证状态",
    "缺失行为",
]

REQUIRED_EVIDENCE_GATES = [
    "competitive-analysis",
    "comps-analysis",
    "idea-generation",
    "概念标签不能单独作为核心入选依据",
    "行情和估值字段必须带数据时间",
    "idea 入选必须同时具备主题暴露、估值或质量证据、why-now、风险和失效条件",
]

REQUIRED_RESEARCH_PACK_FILES = [
    "source_manifest.json",
    "peer_universe.csv",
    "market_snapshot.csv",
    "financial_summary.csv",
    "financial_statements.csv",
    "company_exposure.md",
    "events_and_risks.md",
    "research_reports.csv",
    "research_reports/",
    "block_trades.csv",
    "shareholder_counts.csv",
    "investor_interactions.csv",
]

REQUIRED_RESEARCH_PACK_FIELDS = [
    "source_type",
    "source_name",
    "data_time",
    "period_or_basis",
    "verification_status",
    "missing_behavior",
    "code",
    "name",
    "exchange",
    "peer_group",
    "theme_role",
    "exposure_source_ref",
    "snapshot_time",
    "revenue",
    "net_profit",
    "roe",
    "report_id",
    "scope_type",
    "profit_forecast_raw",
    "local_pdf_path",
    "block_trade_id",
    "deal_volume_shares",
    "premium_discount_pct_basis",
    "shareholder_snapshot_id",
    "statistical_end_date",
    "announcement_date",
    "holder_count",
    "holder_count_change_basis",
    "holder_count_change_pct_basis",
    "average_holding_shares",
    "total_shares",
    "interaction_id",
    "platform",
    "source_record_id",
    "question_time",
    "answer_time",
    "question_source",
    "answerer",
    "source_url",
    "statement_item_id",
    "security_code",
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
    "basis",
]

REQUIRED_INTERACTION_BOUNDARIES = [
    "问题中的断言不构成事实",
    "公司回复需与公告或定期报告交叉验证",
    "深交所互动易",
    "上证e互动",
    "financial_summary.csv",
    "financial_statements.csv",
    "statement_scope=来源缺失",
    "financial_statement_historical_version_unavailable",
    "financial_statement_schema",
    "financial_statement_unsupported",
    "financial_statement_balance_sheet",
    "financial_statement_income_statement",
    "financial_statement_cash_flow",
    "financial_statement_input",
    "point_in_time",
    "year_to_date",
    "只表示来源",
    "不得用摘要字段倒推三张报表",
    "口径不可比",
]

REQUIRED_COMPS_BOUNDARIES = [
    "financial_statements.csv",
    "normalized_line_item",
    "value_semantics",
    "statement_scope=来源缺失",
    "point_in_time",
    "year_to_date",
    "口径不可比",
    "不新增计算器",
]

REQUIRED_DOC_TOKENS = [
    "financial_statements.csv",
    "--financial-statement-source",
    "--financial-statement-period-limit",
    "--financial-statement-fixture-scenario",
    "--skip-financial-statements",
    "statement_scope=来源缺失",
    "verified",
]


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_contract() -> list[str]:
    errors: list[str] = []
    text = _read(SOURCE)

    for heading in REQUIRED_SECTIONS:
        if heading not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing section {heading}")

    for source_type in REQUIRED_SOURCE_TYPES:
        if source_type not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing source type `{source_type}`")

    for field in REQUIRED_METADATA_FIELDS:
        if field not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing metadata field `{field}`")

    for phrase in REQUIRED_EVIDENCE_GATES:
        if phrase not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing evidence gate `{phrase}`")

    for filename in REQUIRED_RESEARCH_PACK_FILES:
        if filename not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing research-pack file `{filename}`")

    for field in REQUIRED_RESEARCH_PACK_FIELDS:
        if field not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing research-pack field `{field}`")

    for phrase in REQUIRED_INTERACTION_BOUNDARIES:
        if phrase not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing interaction boundary `{phrase}`")

    if SOURCE.is_file() and BUNDLED.is_file() and _read(SOURCE) != _read(BUNDLED):
        errors.append(
            "a-share-data-sources bundled copy drifted from vertical source "
            "(run scripts/sync-agent-skills.py)"
        )

    comps_text = _read(COMPS_SOURCE)
    for phrase in REQUIRED_COMPS_BOUNDARIES:
        if phrase not in comps_text:
            errors.append(f"{COMPS_SOURCE.relative_to(ROOT)} missing comps boundary `{phrase}`")
    if COMPS_SOURCE.is_file() and COMPS_BUNDLED.is_file() and _read(COMPS_SOURCE) != _read(COMPS_BUNDLED):
        errors.append(
            "a-share-comps-analysis bundled copy drifted from vertical source "
            "(run scripts/sync-agent-skills.py)"
        )
    for document in [QUICK_START, ROADMAP, MANAGED_README]:
        document_text = _read(document)
        for token in REQUIRED_DOC_TOKENS:
            if token not in document_text:
                errors.append(f"{document.relative_to(ROOT)} missing downstream token `{token}`")
    for document in [AGENT_PROMPT, DATA_PREP_AGENT]:
        document_text = _read(document)
        for token in ["financial_statements.csv", "statement_scope=来源缺失"]:
            if token not in document_text:
                errors.append(f"{document.relative_to(ROOT)} missing financial statement token `{token}`")

    return errors


def main() -> int:
    errors = validate_contract()
    if errors:
        print(f"FAIL — {len(errors)} A-share data contract issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  ✗ {error}", file=sys.stderr)
        return 1
    print("OK — A-share data source contract checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
