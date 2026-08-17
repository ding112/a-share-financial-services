#!/usr/bin/env python3
"""验证 A 股下游 Skill 与 Agent handoff 契约。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPS_SOURCE = ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-comps-analysis/SKILL.md"
COMPS_BUNDLED = ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-comps-analysis/SKILL.md"
AGENT_PROMPT = ROOT / "plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md"
DATA_PREP_AGENT = ROOT / "managed-agent-cookbooks/a-share-market-researcher/subagents/data-prep.yaml"
COMPS_BOUNDARIES = (
    "financial_statements.csv",
    "normalized_line_item",
    "value_semantics",
    "statement_scope=来源缺失",
    "point_in_time",
    "year_to_date",
    "口径不可比",
    "不新增计算器",
)
HANDOFF_TOKENS = ("financial_statements.csv", "statement_scope=来源缺失")


def validate_contract() -> list[str]:
    errors: list[str] = []
    if not COMPS_SOURCE.is_file() or not COMPS_BUNDLED.is_file():
        errors.append("A-share comps skill source or bundle is missing")
    else:
        source_text = COMPS_SOURCE.read_text(encoding="utf-8")
        for token in COMPS_BOUNDARIES:
            if token not in source_text:
                errors.append(f"{COMPS_SOURCE.relative_to(ROOT)} missing comps boundary `{token}`")
        if source_text != COMPS_BUNDLED.read_text(encoding="utf-8"):
            errors.append("a-share-comps-analysis bundled copy drifted from vertical source")

    for document in (AGENT_PROMPT, DATA_PREP_AGENT):
        if not document.is_file():
            errors.append(f"missing Agent handoff: {document.relative_to(ROOT)}")
            continue
        text = document.read_text(encoding="utf-8")
        for token in HANDOFF_TOKENS:
            if token not in text:
                errors.append(f"{document.relative_to(ROOT)} missing handoff token `{token}`")
    return errors


def main() -> int:
    errors = validate_contract()
    if errors:
        print(f"FAIL — {len(errors)} A-share Agent handoff issue(s):")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print("OK — A-share Agent handoff contract checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
