#!/usr/bin/env python3
"""Validate the A-share data source contract skill."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/SKILL.md"
BUNDLED = ROOT / "plugins/agent-plugins/a-share-market-researcher/skills/a-share-data-sources/SKILL.md"

REQUIRED_SECTIONS = [
    "## 研究事实类型",
    "## 来源等级契约",
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

    if SOURCE.is_file() and BUNDLED.is_file() and _read(SOURCE) != _read(BUNDLED):
        errors.append(
            "a-share-data-sources bundled copy drifted from vertical source "
            "(run scripts/sync-agent-skills.py)"
        )

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
