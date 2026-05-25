#!/usr/bin/env python3
"""Generate a static A-share research dashboard from local artifacts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from datetime import datetime
from pathlib import Path

from a_share_output_paths import stage_dir

MISSING = "来源缺失"
SKIP_NUMERIC = {MISSING, "待验证", "口径不可比", "亏损", "不适用", ""}
MONEY_FIELDS = {
    "market_cap",
    "float_market_cap",
    "revenue",
    "net_profit",
    "deducted_net_profit",
    "operating_cash_flow",
    "amount",
    "hold_market_cap",
}
PERCENT_FIELDS = {
    "return_5d",
    "return_20d",
    "revenue_growth",
    "gross_margin",
    "net_margin",
    "roe",
    "asset_liability_ratio",
    "pct_change",
    "turnover_rate",
}
MARKDOWN_PREVIEW_LINES = 120


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", required=True, help="Chinese theme shown in the dashboard.")
    parser.add_argument("--research-pack", required=True, help="Directory containing research-pack files.")
    parser.add_argument("--comps-dir", required=True, help="Directory containing comps artifacts.")
    parser.add_argument("--handoff-dir", required=True, help="Directory containing handoff artifacts.")
    parser.add_argument("--note-dir", required=True, help="Directory containing note assembly artifacts.")
    parser.add_argument(
        "--output-dir",
        help="Directory where index.html is written. Defaults to out/<theme>/dashboard.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def clean_value(value: object | None) -> str:
    if value is None:
        return MISSING
    text = str(value).strip()
    return text if text else MISSING


def escape(value: object | None) -> str:
    return html.escape(clean_value(value), quote=True)


def to_number(value: object | None) -> float | None:
    text = clean_value(value).replace(",", "").replace("%", "").strip()
    if text in SKIP_NUMERIC:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_money(value: object | None) -> str:
    number = to_number(value)
    if number is None:
        return clean_value(value)
    absolute = abs(number)
    if absolute >= 1_0000_0000_0000:
        return f"{number / 1_0000_0000_0000:.2f} 万亿"
    if absolute >= 1_0000_0000:
        return f"{number / 1_0000_0000:.2f} 亿"
    return clean_value(value)


def format_percent(value: object | None) -> str:
    number = to_number(value)
    if number is None:
        return clean_value(value)
    return f"{number:.1f}%"


def format_metric_value(field_name: str, value: object | None) -> str:
    if field_name in MONEY_FIELDS:
        return format_money(value)
    if field_name in PERCENT_FIELDS:
        return format_percent(value)
    return clean_value(value)


def sanitize_remote_url_text(text: str) -> str:
    return text.replace("https://", "https[:]//").replace("http://", "http[:]//")


def index_by_code(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("code", ""): row for row in rows if row.get("code")}


def rows_by_code(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        code = row.get("code", "")
        if code:
            result.setdefault(code, []).append(row)
    return result


def first_value(*values: object | None) -> str:
    for value in values:
        cleaned = clean_value(value)
        if cleaned != MISSING:
            return cleaned
    return MISSING


def collect_codes(*row_sets: list[dict[str, str]]) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for rows in row_sets:
        for row in rows:
            code = row.get("code", "")
            if code and code not in seen:
                codes.append(code)
                seen.add(code)
    return codes


def quality_counts(comps_rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {"可用": 0, MISSING: 0, "口径不可比": 0, "其他": 0}
    for row in comps_rows:
        flag = clean_value(row.get("data_quality_flag"))
        if flag in counts:
            counts[flag] += 1
        else:
            counts["其他"] += 1
    return counts


def link_to(output_dir: Path, target: Path, label: str) -> str:
    if not target.is_file():
        return f"<span class=\"muted\">{escape(label)} 未生成</span>"
    href = os.path.relpath(target, output_dir)
    return f"<a href=\"{html.escape(href, quote=True)}\">{escape(label)}</a>"


def artifact_links(note_dir: Path, output_dir: Path) -> str:
    links = [link_to(output_dir, note_dir / "research_assembly_manifest.json", "研究组装 manifest")]
    for path in sorted(note_dir.glob("*.md")):
        links.append(link_to(output_dir, path, path.name))
    workbook_dir = note_dir.parent / "workbook"
    for path in sorted(workbook_dir.glob("*.xlsx")):
        links.append(link_to(output_dir, path, path.name))
    for path in sorted(note_dir.glob("*.xlsx")):
        links.append(link_to(output_dir, path, path.name))
    return " · ".join(links)


def render_inline_markdown(text: str) -> str:
    escaped_parts = [html.escape(sanitize_remote_url_text(part), quote=True) for part in text.split("`")]
    for index in range(1, len(escaped_parts), 2):
        escaped_parts[index] = f"<code>{escaped_parts[index]}</code>"
    return "".join(escaped_parts)


def heading_level(line: str) -> int:
    stripped = line.lstrip()
    level = len(stripped) - len(stripped.lstrip("#"))
    if 1 <= level <= 6 and stripped[level : level + 1] == " ":
        return level
    return 0


def is_ordered_list_item(line: str) -> bool:
    stripped = line.lstrip()
    dot_index = stripped.find(". ")
    return dot_index > 0 and stripped[:dot_index].isdigit()


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    allowed = {"|", "-", ":", " "}
    return bool(stripped) and all(char in allowed for char in stripped)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_markdown_table(lines: list[str]) -> str:
    headers = split_table_row(lines[0])
    rows = [split_table_row(line) for line in lines[2:]]
    head = "".join(f"<th>{render_inline_markdown(header)}</th>" for header in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{render_inline_markdown(cell)}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    return f"<div class=\"md-table\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def render_markdown_preview(text: str) -> str:
    lines = text.splitlines()
    parts: list[str] = []
    list_state: str | None = None

    def close_list() -> None:
        nonlocal list_state
        if list_state:
            parts.append(f"</{list_state}>")
            list_state = None

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            close_list()
            index += 1
            continue

        if stripped.startswith("```"):
            close_list()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            parts.append(f"<pre><code>{html.escape(sanitize_remote_url_text(chr(10).join(code_lines)), quote=True)}</code></pre>")
            continue

        if index + 1 < len(lines) and "|" in stripped and is_table_separator(lines[index + 1]):
            close_list()
            table_lines = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                table_lines.append(lines[index])
                index += 1
            parts.append(render_markdown_table(table_lines))
            continue

        level = heading_level(line)
        if level:
            close_list()
            text_part = line.lstrip()[level + 1 :]
            parts.append(f"<h{level}>{render_inline_markdown(text_part)}</h{level}>")
            index += 1
            continue

        if stripped.startswith(("- ", "* ", "+ ")):
            if list_state != "ul":
                close_list()
                parts.append("<ul>")
                list_state = "ul"
            parts.append(f"<li>{render_inline_markdown(stripped[2:])}</li>")
            index += 1
            continue

        if is_ordered_list_item(line):
            dot_index = stripped.find(". ")
            if list_state != "ol":
                close_list()
                parts.append("<ol>")
                list_state = "ol"
            parts.append(f"<li>{render_inline_markdown(stripped[dot_index + 2:])}</li>")
            index += 1
            continue

        if stripped.startswith(">"):
            close_list()
            quote_text = stripped[1:].strip()
            parts.append(f"<blockquote>{render_inline_markdown(quote_text)}</blockquote>")
            index += 1
            continue

        close_list()
        parts.append(f"<p>{render_inline_markdown(stripped)}</p>")
        index += 1

    close_list()
    return "".join(parts)


def render_markdown_notes(note_dir: Path, output_dir: Path) -> str:
    note_paths = sorted(note_dir.glob("*.md"))
    if not note_paths:
        return f"<p class=\"empty\">{MISSING}：未生成 Markdown 研究笔记。</p>"
    cards = []
    for path in note_paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        truncated = len(lines) > MARKDOWN_PREVIEW_LINES
        preview_text = "\n".join(lines[:MARKDOWN_PREVIEW_LINES])
        truncation_note = ""
        if truncated:
            truncation_note = "<p class=\"empty\">已截断，可打开原文件查看全文。</p>"
        cards.append(
            "<article class=\"note-card\">"
            f"<div class=\"note-title\"><h3>{escape(path.name)}</h3>{link_to(output_dir, path, '打开原文件')}</div>"
            f"<div class=\"markdown-body\">{render_markdown_preview(preview_text)}</div>{truncation_note}"
            "</article>"
        )
    return f"<div class=\"notes-grid\">{''.join(cards)}</div>"


def risk_text(
    code: str,
    idea: dict[str, str],
    risk_by_code: dict[str, list[dict[str, str]]],
    exception_by_code: dict[str, list[dict[str, str]]],
) -> str:
    parts = [clean_value(idea.get("major_risks"))]
    for row in risk_by_code.get(code, [])[:2]:
        parts.append(first_value(row.get("risk_type"), row.get("risk_detail")))
    for row in exception_by_code.get(code, [])[:2]:
        parts.append(first_value(row.get("exception_type"), row.get("reason")))
    usable = [part for part in parts if part != MISSING]
    return "；".join(usable) if usable else MISSING


def build_stock_rows(
    peers: list[dict[str, str]],
    comps_rows: list[dict[str, str]],
    idea_rows: list[dict[str, str]],
    risk_rows: list[dict[str, str]],
    exception_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    peers_by_code = index_by_code(peers)
    comps_by_code = index_by_code(comps_rows)
    ideas_by_code = index_by_code(idea_rows)
    risks_by_code = rows_by_code(risk_rows)
    exceptions_by_code = rows_by_code(exception_rows)
    rows: list[dict[str, str]] = []
    for code in collect_codes(peers, comps_rows, idea_rows):
        peer = peers_by_code.get(code, {})
        comps = comps_by_code.get(code, {})
        idea = ideas_by_code.get(code, {})
        rows.append(
            {
                "code": code,
                "name": first_value(peer.get("name"), comps.get("name"), idea.get("name")),
                "theme_role": first_value(peer.get("theme_role"), comps.get("theme_role"), idea.get("theme_role")),
                "research_priority": clean_value(idea.get("research_priority")),
                "data_quality_flag": clean_value(comps.get("data_quality_flag")),
                "risk_summary": risk_text(code, idea, risks_by_code, exceptions_by_code),
                "observation": first_value(idea.get("why_now"), idea.get("catalyst")),
                "failure_conditions": clean_value(idea.get("failure_conditions")),
            }
        )
    return rows


def table(headers: list[str], rows: list[list[object]], empty_text: str) -> str:
    if not rows:
        return f"<p class=\"empty\">{escape(empty_text)}</p>"
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"


def badge(value: str) -> str:
    css_class = "badge"
    if value == "可用":
        css_class += " good"
    elif value in {MISSING, "待验证", "口径不可比"}:
        css_class += " warn"
    return f"<span class=\"{css_class}\">{escape(value)}</span>"


def render_stock_table(stock_rows: list[dict[str, str]]) -> str:
    if not stock_rows:
        return f"<p class=\"empty\">{MISSING}：未读取到股票池。</p>"
    body = []
    for row in stock_rows:
        body.append(
            "<tr>"
            f"<td class=\"code\">{escape(row['code'])}</td>"
            f"<td>{escape(row['name'])}</td>"
            f"<td>{escape(row['theme_role'])}</td>"
            f"<td>{escape(row['research_priority'])}</td>"
            f"<td>{badge(row['data_quality_flag'])}</td>"
            f"<td>{escape(row['risk_summary'])}</td>"
            f"<td>{escape(row['observation'])}</td>"
            f"<td>{escape(row['failure_conditions'])}</td>"
            "</tr>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>代码</th><th>简称</th><th>主题角色</th><th>研究优先级</th>"
        "<th>数据质量</th><th>风险摘要</th><th>观察条件</th><th>失效条件</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def render_comps_table(comps_rows: list[dict[str, str]], financial_rows: list[dict[str, str]]) -> str:
    financial_by_code = index_by_code(financial_rows)
    rows = [
        [
            row.get("code"),
            row.get("name"),
            format_money(row.get("market_cap")),
            row.get("pe_ttm"),
            row.get("pb"),
            row.get("ps_ttm"),
            format_percent(row.get("return_5d")),
            format_percent(row.get("return_20d")),
            format_money(row.get("revenue")),
            format_money(row.get("net_profit")),
            format_percent(first_value(financial_by_code.get(row.get("code", ""), {}).get("net_margin"), row.get("net_margin"))),
            format_percent(first_value(financial_by_code.get(row.get("code", ""), {}).get("gross_margin"), row.get("gross_margin"))),
            format_percent(row.get("roe")),
            row.get("data_quality_flag"),
        ]
        for row in comps_rows
    ]
    return table(
        ["代码", "简称", "市值", "PE TTM", "PB", "PS", "5日", "20日", "收入", "净利", "净利率", "毛利率", "ROE", "数据质量"],
        rows,
        f"{MISSING}：未生成 comps_main.csv。",
    )


def scatter_points(rows: list[dict[str, str]], x_field: str, y_field: str) -> tuple[list[dict[str, object]], int]:
    points: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        x_value = to_number(row.get(x_field))
        y_value = to_number(row.get(y_field))
        if x_value is None or y_value is None:
            skipped += 1
            continue
        points.append(
            {
                "code": clean_value(row.get("code")),
                "name": clean_value(row.get("name")),
                "x": x_value,
                "y": y_value,
            }
        )
    return points, skipped


def scale(value: float, minimum: float, maximum: float, start: float, end: float) -> float:
    if maximum == minimum:
        return (start + end) / 2
    return start + (value - minimum) * (end - start) / (maximum - minimum)


def render_scatter(rows: list[dict[str, str]], x_field: str, y_field: str, title: str, x_label: str, y_label: str) -> str:
    points, skipped = scatter_points(rows, x_field, y_field)
    if not points:
        return (
            "<div class=\"chart\"><h3>{}</h3><p class=\"empty\">{}：字段不足，无法绘制。</p></div>"
        ).format(escape(title), MISSING)
    width, height = 520, 320
    pad_left, pad_right, pad_top, pad_bottom = 58, 26, 34, 50
    xs = [float(point["x"]) for point in points]
    ys = [float(point["y"]) for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    circles = []
    labels = []
    for point in points:
        x = scale(float(point["x"]), min_x, max_x, pad_left, width - pad_right)
        y = scale(float(point["y"]), min_y, max_y, height - pad_bottom, pad_top)
        name = escape(point["name"])
        x_display = escape(format_metric_value(x_field, point["x"]))
        y_display = escape(format_metric_value(y_field, point["y"]))
        circles.append(
            f"<circle cx=\"{x:.1f}\" cy=\"{y:.1f}\" r=\"5.5\"><title>{name}：{escape(x_label)} {x_display}，{escape(y_label)} {y_display}</title></circle>"
        )
        labels.append(f"<text x=\"{x + 7:.1f}\" y=\"{y - 7:.1f}\" class=\"point-label\">{name}</text>")
    axis = (
        f"<line x1=\"{pad_left}\" y1=\"{height - pad_bottom}\" x2=\"{width - pad_right}\" y2=\"{height - pad_bottom}\" />"
        f"<line x1=\"{pad_left}\" y1=\"{height - pad_bottom}\" x2=\"{pad_left}\" y2=\"{pad_top}\" />"
        f"<text x=\"{width / 2:.1f}\" y=\"{height - 10}\" class=\"axis-label\">{escape(x_label)}</text>"
        f"<text x=\"14\" y=\"{height / 2:.1f}\" class=\"axis-label vertical\">{escape(y_label)}</text>"
        f"<text x=\"{pad_left}\" y=\"{height - 30}\" class=\"tick\">{escape(format_metric_value(x_field, min_x))}</text>"
        f"<text x=\"{width - pad_right - 68}\" y=\"{height - 30}\" class=\"tick\">{escape(format_metric_value(x_field, max_x))}</text>"
        f"<text x=\"18\" y=\"{height - pad_bottom}\" class=\"tick\">{escape(format_metric_value(y_field, min_y))}</text>"
        f"<text x=\"18\" y=\"{pad_top + 4}\" class=\"tick\">{escape(format_metric_value(y_field, max_y))}</text>"
    )
    note = f"已绘制 {len(points)} 个点；{skipped} 个点因字段缺失或不可比被跳过。"
    return (
        f"<div class=\"chart\"><h3>{escape(title)}</h3>"
        f"<svg viewBox=\"0 0 {width} {height}\" role=\"img\" aria-label=\"{escape(title)}\">"
        f"<g class=\"axis\">{axis}</g><g class=\"points\">{''.join(circles)}</g><g>{''.join(labels)}</g>"
        f"</svg><p class=\"chart-note\">{escape(note)}</p></div>"
    )


def render_sources(
    source_manifest: dict[str, object],
    gap_rows: list[dict[str, str]],
    exception_rows: list[dict[str, str]],
    risk_rows: list[dict[str, str]],
    note_dir: Path,
    output_dir: Path,
) -> str:
    files = source_manifest.get("files", [])
    source_rows: list[list[object]] = []
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict):
                source_rows.append(
                    [
                        item.get("file"),
                        item.get("source_type"),
                        item.get("source_name"),
                        item.get("data_time"),
                        item.get("verification_status"),
                        item.get("missing_behavior"),
                    ]
                )
    gap_table = table(
        ["代码", "字段", "用途", "缺口原因", "缺失行为"],
        [[r.get("code"), r.get("field_name"), r.get("required_for"), r.get("gap_reason"), r.get("missing_behavior")] for r in gap_rows[:30]],
        "暂无数据缺口记录。",
    )
    risk_table = table(
        ["代码", "简称", "风险类型", "风险详情", "处理"],
        [[r.get("code"), r.get("name"), r.get("risk_type"), r.get("risk_detail"), r.get("idea_generation_action")] for r in risk_rows[:30]],
        "暂无风险登记记录。",
    )
    exception_table = table(
        ["代码", "简称", "异常类型", "指标", "处理", "原因"],
        [[r.get("code"), r.get("name"), r.get("exception_type"), r.get("metric"), r.get("action"), r.get("reason")] for r in exception_rows[:30]],
        "暂无异常项记录。",
    )
    source_table = table(
        ["文件", "来源类型", "来源名称", "数据时间", "验证状态", "缺失行为"],
        source_rows,
        f"{MISSING}：未读取到 source_manifest.json。",
    )
    links = artifact_links(note_dir, output_dir)
    return (
        f"<div class=\"subsection\"><h3>风险登记</h3>{risk_table}</div>"
        f"<div class=\"subsection\"><h3>数据缺口</h3>{gap_table}</div>"
        f"<div class=\"subsection\"><h3>异常项</h3>{exception_table}</div>"
        f"<div class=\"subsection\"><h3>来源覆盖</h3>{source_table}</div>"
        f"<p class=\"links\">{links}</p>"
    )


def load_dashboard_inputs(research_pack: Path, comps_dir: Path, handoff_dir: Path, note_dir: Path) -> dict[str, object]:
    return {
        "peers": read_csv(research_pack / "peer_universe.csv"),
        "financial_summary": read_csv(research_pack / "financial_summary.csv"),
        "source_manifest": read_json(research_pack / "source_manifest.json"),
        "comps_main": read_csv(comps_dir / "comps_main.csv"),
        "comps_data_gaps": read_csv(comps_dir / "comps_data_gaps.csv"),
        "comps_exceptions": read_csv(comps_dir / "comps_exceptions.csv"),
        "idea_inputs": read_csv(handoff_dir / "idea_inputs.csv"),
        "idea_risk_register": read_csv(handoff_dir / "idea_risk_register.csv"),
        "research_assembly_manifest": read_json(note_dir / "research_assembly_manifest.json"),
    }


def build_html(theme: str, inputs: dict[str, object], paths: dict[str, Path]) -> str:
    peers = inputs["peers"]
    financial_rows = inputs["financial_summary"]
    source_manifest = inputs["source_manifest"]
    comps_rows = inputs["comps_main"]
    gap_rows = inputs["comps_data_gaps"]
    exception_rows = inputs["comps_exceptions"]
    idea_rows = inputs["idea_inputs"]
    risk_rows = inputs["idea_risk_register"]
    assert isinstance(peers, list)
    assert isinstance(financial_rows, list)
    assert isinstance(source_manifest, dict)
    assert isinstance(comps_rows, list)
    assert isinstance(gap_rows, list)
    assert isinstance(exception_rows, list)
    assert isinstance(idea_rows, list)
    assert isinstance(risk_rows, list)

    stock_rows = build_stock_rows(peers, comps_rows, idea_rows, risk_rows, exception_rows)
    counts = quality_counts(comps_rows)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overview_items = [
        ("主题", theme),
        ("股票数量", str(len(stock_rows))),
        ("数据可用", str(counts["可用"])),
        ("来源缺失", str(counts[MISSING])),
        ("口径不可比", str(counts["口径不可比"])),
        ("生成时间", generated_at),
    ]
    overview = "".join(
        f"<div class=\"metric\"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in overview_items
    )
    charts = (
        render_scatter(comps_rows, "pe_ttm", "roe", "PE TTM vs ROE", "PE TTM", "ROE")
        + render_scatter(comps_rows, "market_cap", "return_20d", "市值 vs 20 日表现", "市值", "20 日表现")
    )
    notes = render_markdown_notes(paths["note_dir"], paths["output_dir"])
    sources = render_sources(
        source_manifest,
        gap_rows,
        exception_rows,
        risk_rows,
        paths["note_dir"],
        paths["output_dir"],
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(theme)} - A 股研究看板</title>
  <style>
    :root {{
      --ink: #172026;
      --muted: #61707a;
      --line: #d7dde0;
      --paper: #f6f3eb;
      --panel: #fffdf8;
      --accent: #b7352d;
      --good: #1f7a4d;
      --warn: #b7791f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: "Iowan Old Style", "Songti SC", "Noto Serif CJK SC", Georgia, serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px; }}
    header {{ border-bottom: 3px solid var(--ink); padding-bottom: 18px; margin-bottom: 22px; }}
    h1 {{ font-size: 34px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 21px; margin: 0 0 12px; }}
    h3 {{ font-size: 16px; margin: 0 0 10px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 18px;
      margin: 16px 0;
      box-shadow: 0 1px 0 rgba(23, 32, 38, 0.05);
    }}
    .lede {{ color: var(--muted); margin: 0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; }}
    .metric {{ border-left: 3px solid var(--accent); background: #fdf8ed; padding: 10px 12px; min-height: 72px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; font-size: 22px; margin-top: 4px; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: white; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 9px; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #eee7da; white-space: nowrap; }}
    .code {{ font-family: "SFMono-Regular", Consolas, monospace; white-space: nowrap; }}
    .badge {{ display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 1px 8px; white-space: nowrap; }}
    .badge.good {{ border-color: var(--good); color: var(--good); }}
    .badge.warn {{ border-color: var(--warn); color: var(--warn); }}
    .charts {{ display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 14px; }}
    .chart {{ border: 1px solid var(--line); border-radius: 6px; padding: 14px; background: white; }}
    svg {{ width: 100%; height: auto; }}
    .axis line {{ stroke: #67727a; stroke-width: 1; }}
    .tick, .axis-label, .point-label {{ fill: #526069; font-size: 11px; }}
    .vertical {{ transform: rotate(-90deg); transform-origin: 14px center; }}
    .points circle {{ fill: var(--accent); opacity: 0.84; }}
    .chart-note, .empty, .muted {{ color: var(--muted); }}
    .notes-grid {{ display: grid; grid-template-columns: repeat(2, minmax(360px, 1fr)); gap: 14px; }}
    .note-card {{ background: white; border: 1px solid var(--line); border-radius: 6px; padding: 14px; max-height: 720px; overflow: auto; }}
    .note-title {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; border-bottom: 1px solid var(--line); margin-bottom: 12px; padding-bottom: 8px; }}
    .note-title a {{ color: var(--accent); white-space: nowrap; }}
    .markdown-body {{ font-size: 13px; line-height: 1.58; }}
    .markdown-body h1 {{ font-size: 22px; margin: 16px 0 8px; }}
    .markdown-body h2 {{ font-size: 18px; margin: 16px 0 8px; }}
    .markdown-body h3 {{ font-size: 15px; margin: 14px 0 6px; }}
    .markdown-body h4, .markdown-body h5, .markdown-body h6 {{ font-size: 13px; margin: 12px 0 6px; }}
    .markdown-body p {{ margin: 7px 0; }}
    .markdown-body ul, .markdown-body ol {{ margin: 7px 0 10px 20px; padding: 0; }}
    .markdown-body blockquote {{ margin: 8px 0; padding: 7px 10px; border-left: 3px solid var(--accent); background: #fdf8ed; color: var(--muted); }}
    .markdown-body pre {{ overflow-x: auto; background: #172026; color: #fffdf8; padding: 10px; border-radius: 4px; }}
    .markdown-body code {{ font-family: "SFMono-Regular", Consolas, monospace; font-size: 12px; }}
    .md-table {{ overflow-x: auto; margin: 10px 0; }}
    .md-table table {{ font-size: 12px; }}
    .subsection {{ margin-top: 16px; }}
    .links a {{ color: var(--accent); }}
    @media (max-width: 900px) {{
      main {{ padding: 16px; }}
      .metrics, .charts, .notes-grid {{ grid-template-columns: 1fr; }}
      .note-title {{ display: block; }}
      h1 {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{escape(theme)} A 股研究看板</h1>
    <p class="lede">用于复核本地 research-pack、comps、handoff 和 note 产物；不构成投资建议。</p>
  </header>
  <section><h2>总览</h2><div class="metrics">{overview}</div></section>
  <section><h2>股票池</h2>{render_stock_table(stock_rows)}</section>
  <section><h2>Comps</h2>{render_comps_table(comps_rows, financial_rows)}</section>
  <section><h2>图表区</h2><div class="charts">{charts}</div></section>
  <section><h2>研究笔记</h2>{notes}</section>
  <section><h2>风险与来源</h2>{sources}</section>
</main>
</body>
</html>
"""


def write_dashboard(theme: str, research_pack: Path, comps_dir: Path, handoff_dir: Path, note_dir: Path, output_dir: Path) -> Path:
    inputs = load_dashboard_inputs(research_pack, comps_dir, handoff_dir, note_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_text = build_html(
        theme,
        inputs,
        {
            "research_pack": research_pack,
            "comps_dir": comps_dir,
            "handoff_dir": handoff_dir,
            "note_dir": note_dir,
            "output_dir": output_dir,
        },
    )
    output_path = output_dir / "index.html"
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    output_path = write_dashboard(
        args.theme,
        Path(args.research_pack),
        Path(args.comps_dir),
        Path(args.handoff_dir),
        Path(args.note_dir),
        Path(args.output_dir) if args.output_dir else stage_dir(args.theme, "dashboard"),
    )
    print(f"wrote A-share dashboard: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
