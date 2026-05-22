#!/usr/bin/env python3
"""Generate A-share competitive and idea handoff artifacts."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

MISSING = "来源缺失"

COMPETITIVE_FIELDS = [
    "code",
    "name",
    "peer_group",
    "theme_role",
    "exposure_summary",
    "exposure_source_ref",
    "market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "revenue",
    "revenue_growth",
    "net_profit",
    "roe",
    "return_5d",
    "return_20d",
    "data_quality_flag",
    "risk_flags",
    "comps_handoff_note",
]

IDEA_FIELDS = [
    "code",
    "name",
    "research_priority",
    "theme_role",
    "theme_exposure",
    "valuation_or_quality_basis",
    "price_performance_basis",
    "liquidity_basis",
    "why_now",
    "catalyst",
    "major_risks",
    "failure_conditions",
    "next_research_questions",
]

RISK_FIELDS = [
    "code",
    "name",
    "risk_type",
    "risk_detail",
    "source_ref",
    "idea_generation_action",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-pack", required=True, help="Directory containing research-pack files.")
    parser.add_argument("--comps-dir", required=True, help="Directory containing phase 5 comps artifacts.")
    parser.add_argument("--output-dir", required=True, help="Directory where handoff files are written.")
    parser.add_argument("--theme", required=True, help="Chinese theme name for summary output.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def index_by_code(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("code", ""): row for row in rows if row.get("code")}


def clean_value(value: str | None) -> str:
    if value is None:
        return MISSING
    stripped = value.strip()
    return stripped if stripped else MISSING


def read_markdown_facts(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    facts: dict[str, list[str]] = {}
    current_code = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        code_match = re.search(r"([0368]\d{5}\.(?:SZ|SH|BJ))", line)
        if code_match:
            current_code = code_match.group(1)
            facts.setdefault(current_code, [])
        if current_code and line.strip() and not line.strip().startswith("#"):
            facts.setdefault(current_code, []).append(line.strip("- |"))
    return {code: "；".join(parts[:4]) for code, parts in facts.items()}


def risk_action(risk_text: str, data_quality_flag: str) -> str:
    if data_quality_flag in {MISSING, "口径不可比", "不适用"}:
        return "降级为待验证或风险排除"
    if risk_text == MISSING:
        return "保留为核心候选但补充风险核查"
    if any(keyword in risk_text for keyword in ["ST", "停牌", "监管", "问询", "诉讼"]):
        return "进入风险排除复核"
    return "保留为候选并在卡片中披露风险"


def research_priority(row: dict[str, str], risk_text: str) -> str:
    if row.get("data_quality_flag") != "可用":
        return "观察候选"
    if any(keyword in risk_text for keyword in ["ST", "停牌", "重大监管"]):
        return "风险排除"
    return "中优先级"


def valuation_basis(row: dict[str, str], gaps_by_code: dict[str, list[str]]) -> str:
    gap_note = "；".join(gaps_by_code.get(row["code"], []))
    basis = (
        f"PE {row.get('pe_ttm', MISSING)}，PB {row.get('pb', MISSING)}，"
        f"PS {row.get('ps_ttm', MISSING)}，ROE {row.get('roe', MISSING)}"
    )
    if gap_note:
        return f"{basis}；数据缺口：{gap_note}"
    return basis


def return_label(value: str | None) -> str:
    cleaned = clean_value(value)
    if cleaned == MISSING:
        return MISSING
    return f"{cleaned}%"


def price_performance_basis(row: dict[str, str]) -> str:
    return (
        f"5日 {return_label(row.get('return_5d'))}，"
        f"20日 {return_label(row.get('return_20d'))}；"
        "仅作 AkShare 前复权短期表现展示，不代表未来结果，也不作为优先级排序依据"
    )


def build_gap_index(gaps: list[dict[str, str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in gaps:
        code = row.get("code", "")
        if not code or code == "ALL":
            continue
        result.setdefault(code, []).append(
            f"{clean_value(row.get('field_name'))}:{clean_value(row.get('gap_reason'))}"
        )
    return result


def build_exception_index(exceptions: list[dict[str, str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in exceptions:
        code = row.get("code", "")
        if not code:
            continue
        result.setdefault(code, []).append(
            f"{clean_value(row.get('metric'))}:{clean_value(row.get('reason'))}"
        )
    return result


def build_competitive_handoff(
    peers: list[dict[str, str]],
    comps_by_code: dict[str, dict[str, str]],
    financial_by_code: dict[str, dict[str, str]],
    exposure_facts: dict[str, str],
    risk_facts: dict[str, str],
    exception_index: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for peer in peers:
        code = clean_value(peer.get("code"))
        comps = comps_by_code.get(code, {})
        financial = financial_by_code.get(code, {})
        exceptions = "；".join(exception_index.get(code, []))
        data_quality = clean_value(comps.get("data_quality_flag"))
        note = "可进入 competitive-analysis 横向比较"
        if data_quality != "可用":
            note = "保留公司但在 competitive-analysis 标记数据不可比"
        rows.append(
            {
                "code": code,
                "name": clean_value(peer.get("name")),
                "peer_group": clean_value(peer.get("peer_group")),
                "theme_role": clean_value(peer.get("theme_role")),
                "exposure_summary": clean_value(exposure_facts.get(code) or peer.get("exposure_summary")),
                "exposure_source_ref": clean_value(peer.get("exposure_source_ref")),
                "market_cap": clean_value(comps.get("market_cap")),
                "pe_ttm": clean_value(comps.get("pe_ttm")),
                "pb": clean_value(comps.get("pb")),
                "ps_ttm": clean_value(comps.get("ps_ttm")),
                "revenue": clean_value(comps.get("revenue")),
                "revenue_growth": clean_value(financial.get("revenue_growth")),
                "net_profit": clean_value(comps.get("net_profit")),
                "roe": clean_value(comps.get("roe")),
                "return_5d": clean_value(comps.get("return_5d")),
                "return_20d": clean_value(comps.get("return_20d")),
                "data_quality_flag": data_quality,
                "risk_flags": clean_value(exceptions or risk_facts.get(code)),
                "comps_handoff_note": note,
            }
        )
    return rows


def build_idea_inputs(
    competitive_rows: list[dict[str, str]],
    gaps_by_code: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in competitive_rows:
        risk_text = clean_value(row.get("risk_flags"))
        priority = research_priority(row, risk_text)
        why_now = "结合 research-pack 的事件和风险文件继续核查政策、订单、产能或财报节点"
        catalyst = "来源缺失" if risk_text == MISSING else "风险或事件文件提供后续核查线索"
        rows.append(
            {
                "code": row["code"],
                "name": row["name"],
                "research_priority": priority,
                "theme_role": row["theme_role"],
                "theme_exposure": row["exposure_summary"],
                "valuation_or_quality_basis": valuation_basis(row, gaps_by_code),
                "price_performance_basis": price_performance_basis(row),
                "liquidity_basis": f"市值 {row['market_cap']}；data_quality {row['data_quality_flag']}",
                "why_now": why_now,
                "catalyst": catalyst,
                "major_risks": risk_text,
                "failure_conditions": "主题暴露证据失效、核心财务字段无法验证、或风险事件升级",
                "next_research_questions": "核查官方披露中的收入暴露；核查催化时间线；核查风险事件状态",
            }
        )
    return rows


def build_risk_register(
    competitive_rows: list[dict[str, str]],
    gaps_by_code: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in competitive_rows:
        gap_note = "；".join(gaps_by_code.get(row["code"], []))
        risk_text = clean_value(row.get("risk_flags"))
        if gap_note:
            rows.append(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "risk_type": "data_gap",
                    "risk_detail": gap_note,
                    "source_ref": "comps_data_gaps.csv",
                    "idea_generation_action": "降级为观察候选",
                }
            )
        rows.append(
            {
                "code": row["code"],
                "name": row["name"],
                "risk_type": "event_or_exception",
                "risk_detail": risk_text,
                "source_ref": "events_and_risks.md / comps_exceptions.csv",
                "idea_generation_action": risk_action(risk_text, row["data_quality_flag"]),
            }
        )
    return rows


def write_summary(
    path: Path,
    theme: str,
    competitive_rows: list[dict[str, str]],
    idea_rows: list[dict[str, str]],
    risk_rows: list[dict[str, str]],
) -> None:
    usable = [row for row in competitive_rows if row["data_quality_flag"] == "可用"]
    core = [row for row in idea_rows if row["research_priority"] in {"高优先级", "中优先级"}]
    downgraded = [row for row in idea_rows if row["research_priority"] not in {"高优先级", "中优先级"}]
    risk_lines = [
        f"- {row['code']} {row['name']}：{row['risk_type']}，{row['idea_generation_action']}。"
        for row in risk_rows[:20]
    ]
    lines = [
        f"# {theme} research handoff summary",
        "",
        "## 竞争格局输入",
        f"- competitive handoff 覆盖 {len(competitive_rows)} 家公司，按 peer_group 和 theme_role 保留分组。",
        "- 每家公司保留 exposure、comps、financial 和 risk 字段，供 competitive-analysis 横向比较。",
        "",
        "## comps 可用性",
        f"- 核心 comps 字段可用公司数：{len(usable)}。",
        "- `data_quality_flag` 非 `可用` 的公司不得直接用于估值或质量排序。",
        "",
        "## idea generation 入选池",
        f"- 中高优先级候选数：{len(core)}。",
        f"- 观察或风险排除候选数：{len(downgraded)}。",
        "",
        "## 风险排除和降级",
    ]
    lines.extend(risk_lines or ["- 未识别到需要降级的风险项。"])
    lines.extend(
        [
            "",
            "## 下一步验证问题",
            "- 核查每个核心候选的官方业务暴露证据是否足够支持入选。",
            "- 核查 why-now 催化是否有日期、来源和公司层面的影响路径。",
            "- 核查 risk register 中的数据缺口和事件风险是否需要降级或剔除。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    pack_dir = Path(args.research_pack)
    comps_dir = Path(args.comps_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    peers = read_csv(pack_dir / "peer_universe.csv")
    if not peers:
        raise SystemExit(f"missing or empty peer_universe.csv in {pack_dir}")

    comps_by_code = index_by_code(read_csv(comps_dir / "comps_main.csv"))
    if not comps_by_code:
        raise SystemExit(f"missing or empty comps_main.csv in {comps_dir}")

    financial_by_code = index_by_code(read_csv(pack_dir / "financial_summary.csv"))
    gaps_by_code = build_gap_index(read_csv(comps_dir / "comps_data_gaps.csv"))
    exception_index = build_exception_index(read_csv(comps_dir / "comps_exceptions.csv"))
    exposure_facts = read_markdown_facts(pack_dir / "company_exposure.md")
    risk_facts = read_markdown_facts(pack_dir / "events_and_risks.md")

    competitive_rows = build_competitive_handoff(
        peers,
        comps_by_code,
        financial_by_code,
        exposure_facts,
        risk_facts,
        exception_index,
    )
    idea_rows = build_idea_inputs(competitive_rows, gaps_by_code)
    risk_rows = build_risk_register(competitive_rows, gaps_by_code)

    write_csv(output_dir / "competitive_handoff.csv", competitive_rows, COMPETITIVE_FIELDS)
    write_csv(output_dir / "idea_inputs.csv", idea_rows, IDEA_FIELDS)
    write_csv(output_dir / "idea_risk_register.csv", risk_rows, RISK_FIELDS)
    write_summary(output_dir / "research_handoff_summary.md", args.theme, competitive_rows, idea_rows, risk_rows)

    print(f"wrote research handoff: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
