#!/usr/bin/env python3
"""Validate the A-share idea generation skill contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-idea-generation/SKILL.md"
BUNDLED = ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-idea-generation/SKILL.md"

REQUIRED_SECTIONS = [
    "## Inputs",
    "## Search criteria",
    "## A-share screening framework",
    "## Thematic sweep",
    "## Idea presentation",
    "## Research priority rules",
    "## Output format",
    "## Guardrails",
]

REQUIRED_SCREEN_DIMENSIONS = [
    "主题暴露",
    "why-now",
    "估值或质量",
    "流动性",
    "催化",
    "风险",
    "失效条件",
]

REQUIRED_OUTPUT_FIELDS = [
    "代码",
    "简称",
    "研究方向",
    "主题角色",
    "一句话逻辑",
    "关键证据",
    "估值或质量依据",
    "催化与为什么是现在",
    "主要风险",
    "失效条件",
    "下一步研究问题",
]

REQUIRED_GUARDRAILS = [
    "不输出买入、卖出、加仓、减仓、目标价或收益承诺",
    "概念标签不能单独作为核心入选依据",
    "没有数据时间的行情或估值字段不能用于优先级排序",
    "风险排除项不得进入核心想法清单",
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

    for dimension in REQUIRED_SCREEN_DIMENSIONS:
        if dimension not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing screen dimension `{dimension}`")

    for field in REQUIRED_OUTPUT_FIELDS:
        if field not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing output field `{field}`")

    for phrase in REQUIRED_GUARDRAILS:
        if phrase not in text:
            errors.append(f"{SOURCE.relative_to(ROOT)} missing guardrail `{phrase}`")

    if SOURCE.is_file() and BUNDLED.is_file() and _read(SOURCE) != _read(BUNDLED):
        errors.append(
            "a-share-idea-generation bundled copy drifted from vertical source "
            "(run scripts/sync-agent-skills.py)"
        )

    return errors


def main() -> int:
    errors = validate_contract()
    if errors:
        print(f"FAIL - {len(errors)} A-share idea generation contract issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A-share idea generation contract checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
