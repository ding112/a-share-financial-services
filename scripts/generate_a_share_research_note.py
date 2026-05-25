#!/usr/bin/env python3
"""Assemble A-share research note and slide outline artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from a_share_output_paths import stage_dir

MISSING = "来源缺失"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-pack", required=True, help="Directory containing research-pack files.")
    parser.add_argument("--comps-dir", required=True, help="Directory containing phase 5 comps artifacts.")
    parser.add_argument("--handoff-dir", required=True, help="Directory containing phase 6 handoff artifacts.")
    parser.add_argument(
        "--output-dir",
        help="Directory where note assembly files are written. Defaults to out/<theme>/note.",
    )
    parser.add_argument("--theme", required=True, help="Chinese theme name for output filenames.")
    parser.add_argument("--angle", default="主题 primer", help="Research angle shown in the note.")
    parser.add_argument("--as-of", default="未指定", help="As-of date shown in the note and manifest.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_text_file(path: Path) -> str:
    if not path.is_file():
        return MISSING
    text = path.read_text(encoding="utf-8").strip()
    return text if text else MISSING


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "", value).strip()
    return cleaned or "A股主题"


def clean_value(value: str | None) -> str:
    if value is None:
        return MISSING
    stripped = value.strip()
    return stripped if stripped else MISSING


def bullet_lines(rows: list[str]) -> str:
    if not rows:
        return f"- {MISSING}"
    return "\n".join(f"- {row}" for row in rows)


def top_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    return rows[:limit]


def load_source_manifest(path: Path) -> dict[str, object]:
    manifest_path = path / "source_manifest.json"
    if not manifest_path.is_file():
        return {"status": "missing_source_manifest", "files": []}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def load_research_inputs(
    research_pack: Path,
    comps_dir: Path,
    handoff_dir: Path,
) -> dict[str, object]:
    return {
        "source_manifest": load_source_manifest(research_pack),
        "peer_universe": read_csv(research_pack / "peer_universe.csv"),
        "company_exposure": read_text_file(research_pack / "company_exposure.md"),
        "events_and_risks": read_text_file(research_pack / "events_and_risks.md"),
        "comps_main": read_csv(comps_dir / "comps_main.csv"),
        "comps_statistics": read_csv(comps_dir / "comps_statistics.csv"),
        "comps_data_gaps": read_csv(comps_dir / "comps_data_gaps.csv"),
        "comps_exceptions": read_csv(comps_dir / "comps_exceptions.csv"),
        "competitive_handoff": read_csv(handoff_dir / "competitive_handoff.csv"),
        "idea_inputs": read_csv(handoff_dir / "idea_inputs.csv"),
        "idea_risk_register": read_csv(handoff_dir / "idea_risk_register.csv"),
        "handoff_summary": read_text_file(handoff_dir / "research_handoff_summary.md"),
    }


def source_summary(manifest: dict[str, object]) -> list[str]:
    files = manifest.get("files", [])
    if not isinstance(files, list) or not files:
        return ["source_manifest.json 缺失或未列出文件；本 note 只能作为用户提供线索的整理稿。"]
    rows: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        rows.append(
            f"{clean_value(str(item.get('file', '')))}："
            f"{clean_value(str(item.get('source_type', '')))} / "
            f"{clean_value(str(item.get('source_name', '')))} / "
            f"{clean_value(str(item.get('data_time', '')))} / "
            f"{clean_value(str(item.get('verification_status', '')))}"
        )
    return rows


def peer_summary(peers: list[dict[str, str]]) -> list[str]:
    rows: list[str] = []
    for row in top_rows(peers, 12):
        rows.append(
            f"{clean_value(row.get('code'))} {clean_value(row.get('name'))}："
            f"{clean_value(row.get('peer_group'))}，"
            f"{clean_value(row.get('theme_role'))}"
        )
    return rows


def competitive_summary(rows: list[dict[str, str]]) -> list[str]:
    result: list[str] = []
    for row in top_rows(rows, 8):
        result.append(
            f"{clean_value(row.get('name'))}（{clean_value(row.get('code'))}）："
            f"{clean_value(row.get('theme_role'))}；"
            f"暴露度：{clean_value(row.get('exposure_summary'))}；"
            f"风险：{clean_value(row.get('risk_flags'))}"
        )
    return result


def comps_summary(rows: list[dict[str, str]], stats: list[dict[str, str]]) -> list[str]:
    result: list[str] = []
    for row in top_rows(rows, 8):
        result.append(
            f"{clean_value(row.get('name'))}：市值 {clean_value(row.get('market_cap'))}，"
            f"PE {clean_value(row.get('pe_ttm'))}，PB {clean_value(row.get('pb'))}，"
            f"PS {clean_value(row.get('ps_ttm'))}，ROE {clean_value(row.get('roe'))}，"
            f"短期表现 5日 {return_label(row.get('return_5d'))} / "
            f"20日 {return_label(row.get('return_20d'))}，"
            f"质量标记 {clean_value(row.get('data_quality_flag'))}"
        )
    if stats:
        stat_bits = [
            f"{clean_value(row.get('metric'))} 中位数 {clean_value(row.get('median'))}"
            for row in top_rows(stats, 6)
        ]
        result.append("统计口径：" + "；".join(stat_bits))
    return result


def return_label(value: str | None) -> str:
    cleaned = clean_value(value)
    if cleaned == MISSING:
        return MISSING
    return f"{cleaned}%"


def short_performance_summary(rows: list[dict[str, str]]) -> list[str]:
    result: list[str] = []
    for row in top_rows(rows, 8):
        result.append(
            f"{clean_value(row.get('name'))}：5日 {return_label(row.get('return_5d'))}，"
            f"20日 {return_label(row.get('return_20d'))}；"
            "短期表现来自前复权收盘价，仅作历史区间表现展示，不代表未来结果。"
        )
    return result


def idea_summary(rows: list[dict[str, str]]) -> list[str]:
    result: list[str] = []
    for row in top_rows(rows, 5):
        result.append(
            f"{clean_value(row.get('name'))}（{clean_value(row.get('code'))}）："
            f"{clean_value(row.get('research_priority'))}；"
            f"{clean_value(row.get('theme_exposure'))}；"
            f"短期表现口径：{clean_value(row.get('price_performance_basis'))}；"
            f"催化：{clean_value(row.get('catalyst'))}；"
            f"失效条件：{clean_value(row.get('failure_conditions'))}"
        )
    return result


def risk_summary(
    risks: list[dict[str, str]],
    gaps: list[dict[str, str]],
    exceptions: list[dict[str, str]],
) -> list[str]:
    result: list[str] = []
    for row in top_rows(risks, 8):
        result.append(
            f"{clean_value(row.get('name'))}：{clean_value(row.get('risk_type'))}，"
            f"{clean_value(row.get('risk_detail'))}；处理："
            f"{clean_value(row.get('idea_generation_action'))}"
        )
    if gaps:
        result.append(f"数据缺口数量：{len(gaps)}，详见 comps_data_gaps.csv。")
    if exceptions:
        result.append(f"异常或不可比项数量：{len(exceptions)}，详见 comps_exceptions.csv。")
    return result


def build_note(theme: str, angle: str, as_of: str, inputs: dict[str, object]) -> str:
    manifest = inputs["source_manifest"]
    peers = inputs["peer_universe"]
    comps_rows = inputs["comps_main"]
    stats = inputs["comps_statistics"]
    gaps = inputs["comps_data_gaps"]
    exceptions = inputs["comps_exceptions"]
    competitive_rows = inputs["competitive_handoff"]
    ideas = inputs["idea_inputs"]
    risks = inputs["idea_risk_register"]

    assert isinstance(manifest, dict)
    assert isinstance(peers, list)
    assert isinstance(comps_rows, list)
    assert isinstance(stats, list)
    assert isinstance(gaps, list)
    assert isinstance(exceptions, list)
    assert isinstance(competitive_rows, list)
    assert isinstance(ideas, list)
    assert isinstance(risks, list)

    return "\n".join(
        [
            f"# {theme}行业研究",
            "",
            f"- 研究角度：{angle}",
            f"- 数据截至：{as_of}",
            "- 材料性质：A 股行业和主题 primer 初稿，仅供分析师复核。",
            "",
            "## 结论摘要",
            "",
            bullet_lines(
                [
                    f"本次覆盖 {len(peers)} 家 A 股样本公司，comps 可用样本 {len(comps_rows)} 家。",
                    f"idea generation 入选池 {len(ideas)} 家；风险登记项 {len(risks)} 条。",
                    "所有数字必须回溯到 source_manifest.json、comps artifact 或 handoff artifact。",
                ]
            ),
            "",
            "## 行业和主题概览",
            "",
            "### 覆盖样本",
            "",
            bullet_lines(peer_summary(peers)),
            "",
            "### 暴露度证据",
            "",
            str(inputs["company_exposure"]),
            "",
            "## 竞争格局",
            "",
            bullet_lines(competitive_summary(competitive_rows)),
            "",
            "## 可比公司分析",
            "",
            bullet_lines(comps_summary(comps_rows, stats)),
            "",
            "### 短期表现口径",
            "",
            bullet_lines(short_performance_summary(comps_rows)),
            "",
            "## 想法清单",
            "",
            bullet_lines(idea_summary(ideas)),
            "",
            "## 风险和待验证事项",
            "",
            bullet_lines(risk_summary(risks, gaps, exceptions)),
            "",
            "### 事件和风险原始摘录",
            "",
            str(inputs["events_and_risks"]),
            "",
            "## 来源和口径",
            "",
            bullet_lines(source_summary(manifest)),
            "",
            "### 交接摘要",
            "",
            str(inputs["handoff_summary"]),
            "",
        ]
    )


def build_slide_outline(theme: str, angle: str, as_of: str, inputs: dict[str, object]) -> str:
    ideas = inputs["idea_inputs"]
    competitive_rows = inputs["competitive_handoff"]
    comps_rows = inputs["comps_main"]
    risks = inputs["idea_risk_register"]
    assert isinstance(ideas, list)
    assert isinstance(competitive_rows, list)
    assert isinstance(comps_rows, list)
    assert isinstance(risks, list)

    idea_bullets = idea_summary(ideas)
    competitive_bullets = competitive_summary(competitive_rows)
    comps_bullets = comps_summary(comps_rows, [])
    risk_bullets = risk_summary(risks, [], [])

    return "\n".join(
        [
            f"# {theme}路演大纲",
            "",
            f"- 研究角度：{angle}",
            f"- 数据截至：{as_of}",
            "- 用途：供 `pptx-author` 或人工制作 slides 时使用。",
            "",
            "## Slide 1：主题和结论",
            "",
            bullet_lines([f"{theme}：{angle}", "本页只陈述研究结论和复核状态，不写交易指令。"]),
            "",
            "## Slide 2：为什么是现在",
            "",
            bullet_lines(["引用 company_exposure.md 与 events_and_risks.md 中的政策、订单、产能、财报或风险线索。"]),
            "",
            "## Slide 3：产业链和竞争格局",
            "",
            bullet_lines(competitive_bullets[:5]),
            "",
            "## Slide 4：可比公司和估值口径",
            "",
            bullet_lines(comps_bullets[:6]),
            "",
            "## Slide 5：想法清单",
            "",
            bullet_lines(idea_bullets),
            "",
            "## Slide 6：风险和待验证问题",
            "",
            bullet_lines(risk_bullets[:6]),
            "",
        ]
    )


def write_manifest(
    output_dir: Path,
    theme: str,
    angle: str,
    as_of: str,
    note_name: str,
    slide_name: str,
    research_pack: Path,
    comps_dir: Path,
    handoff_dir: Path,
) -> None:
    manifest = {
        "theme": theme,
        "angle": angle,
        "as_of": as_of,
        "inputs": {
            "research_pack": str(research_pack),
            "comps_dir": str(comps_dir),
            "handoff_dir": str(handoff_dir),
        },
        "outputs": {
            "research_note": note_name,
            "slide_outline": slide_name,
        },
    }
    (output_dir / "research_assembly_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    research_pack = Path(args.research_pack)
    comps_dir = Path(args.comps_dir)
    handoff_dir = Path(args.handoff_dir)
    output_dir = Path(args.output_dir) if args.output_dir else stage_dir(args.theme, "note")
    output_dir.mkdir(parents=True, exist_ok=True)

    inputs = load_research_inputs(research_pack, comps_dir, handoff_dir)
    filename_theme = safe_filename(args.theme)
    note_name = f"{filename_theme}行业研究.md"
    slide_name = f"{filename_theme}路演大纲.md"

    (output_dir / note_name).write_text(
        build_note(args.theme, args.angle, args.as_of, inputs),
        encoding="utf-8",
    )
    (output_dir / slide_name).write_text(
        build_slide_outline(args.theme, args.angle, args.as_of, inputs),
        encoding="utf-8",
    )
    write_manifest(
        output_dir,
        args.theme,
        args.angle,
        args.as_of,
        note_name,
        slide_name,
        research_pack,
        comps_dir,
        handoff_dir,
    )
    print(f"wrote research note assembly: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
