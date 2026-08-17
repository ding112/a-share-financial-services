#!/usr/bin/env python3
"""验证 A 股研究包的下游文档契约。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    ROOT / "docs/quick-start.md",
    ROOT / "docs/china-equity-trading-roadmap.md",
    ROOT / "managed-agent-cookbooks/a-share-market-researcher/README.md",
)
REQUIRED_TOKENS = (
    "financial_statements.csv",
    "--financial-statement-source",
    "--financial-statement-period-limit",
    "--financial-statement-fixture-scenario",
    "--skip-financial-statements",
    "statement_scope=来源缺失",
    "verified",
    "--include-investor-interactions",
    "默认不执行",
)


def validate_contract() -> list[str]:
    errors: list[str] = []
    for document in DOCUMENTS:
        if not document.is_file():
            errors.append(f"missing documentation: {document.relative_to(ROOT)}")
            continue
        text = document.read_text(encoding="utf-8")
        for token in REQUIRED_TOKENS:
            if token not in text:
                errors.append(f"{document.relative_to(ROOT)} missing documentation token `{token}`")
    return errors


def main() -> int:
    errors = validate_contract()
    if errors:
        print(f"FAIL — {len(errors)} A-share documentation issue(s):")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print("OK — A-share documentation contract checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
