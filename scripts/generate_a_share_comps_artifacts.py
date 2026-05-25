#!/usr/bin/env python3
"""Generate A-share comps artifacts from a local research-pack."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from a_share_output_paths import stage_dir

MISSING = "来源缺失"

MAIN_FIELDS = [
    "code",
    "name",
    "peer_group",
    "theme_role",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "return_5d",
    "return_20d",
    "revenue",
    "net_profit",
    "roe",
    "liquidity_basis",
    "financial_period",
    "data_quality_flag",
]

SOURCE_NOTE_FIELDS = [
    "code",
    "field_name",
    "source_type",
    "source_name",
    "data_time",
    "period_or_basis",
    "verification_status",
    "missing_behavior",
]

EXCEPTION_FIELDS = [
    "code",
    "name",
    "exception_type",
    "metric",
    "observed_value",
    "action",
    "reason",
]

STAT_FIELDS = [
    "metric",
    "sample_size",
    "median",
    "average",
    "minimum",
    "maximum",
    "quartile_1",
    "quartile_3",
    "included_codes",
    "excluded_codes",
]

DATA_GAP_FIELDS = [
    "code",
    "field_name",
    "required_for",
    "gap_reason",
    "missing_behavior",
]

MARKET_FIELDS = [
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
]

PRICE_PERFORMANCE_FIELDS = [
    "return_5d",
    "return_20d",
]

FINANCIAL_FIELDS = [
    "revenue",
    "net_profit",
    "roe",
]

STAT_METRICS = [
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "revenue",
    "net_profit",
    "roe",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-pack", required=True, help="Directory containing research-pack files.")
    parser.add_argument(
        "--output-dir",
        help="Directory where comps artifact files are written. Defaults to out/<theme>/comps.",
    )
    parser.add_argument("--theme", required=True, help="Chinese theme name for comps_summary.md.")
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


def read_source_manifest(pack_dir: Path) -> dict[str, dict[str, str]]:
    manifest_path = pack_dir / "source_manifest.json"
    if not manifest_path.is_file():
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, list):
        return {}
    result: dict[str, dict[str, str]] = {}
    for item in files:
        if isinstance(item, dict) and isinstance(item.get("file"), str):
            key = item["file"]
            if isinstance(item.get("field_group"), str):
                key = f"{key}#{item['field_group']}"
            result[key] = {field: str(value) for field, value in item.items()}
    return result


def clean_value(value: str | None) -> str:
    if value is None:
        return MISSING
    stripped = value.strip()
    return stripped if stripped else MISSING


def to_number(value: str) -> float | None:
    cleaned = value.replace(",", "").replace("%", "").strip()
    if not cleaned or cleaned in {MISSING, "待验证", "口径不可比", "不适用", "亏损"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_number(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    return f"{value:.4f}".rstrip("0").rstrip(".")


def row_quality(row: dict[str, str]) -> str:
    required = ["market_cap", "pe_ttm", "revenue", "net_profit", "roe"]
    if any(row.get(field) == MISSING for field in required):
        return MISSING
    if row.get("pe_ttm") == "亏损":
        return "口径不可比"
    return "可用"


def build_comps_main(
    peers: list[dict[str, str]],
    market_by_code: dict[str, dict[str, str]],
    financial_by_code: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for peer in peers:
        code = clean_value(peer.get("code"))
        market = market_by_code.get(code, {})
        financial = financial_by_code.get(code, {})
        row = {
            "code": code,
            "name": clean_value(peer.get("name")),
            "peer_group": clean_value(peer.get("peer_group")),
            "theme_role": clean_value(peer.get("theme_role")),
            "market_cap": clean_value(market.get("market_cap")),
            "float_market_cap": clean_value(market.get("float_market_cap")),
            "pe_ttm": clean_value(market.get("pe_ttm")),
            "pb": clean_value(market.get("pb")),
            "ps_ttm": clean_value(market.get("ps_ttm")),
            "return_5d": clean_value(market.get("return_5d")),
            "return_20d": clean_value(market.get("return_20d")),
            "revenue": clean_value(financial.get("revenue")),
            "net_profit": clean_value(financial.get("net_profit")),
            "roe": clean_value(financial.get("roe")),
            "liquidity_basis": clean_value(market.get("snapshot_time") or market.get("basis")),
            "financial_period": clean_value(financial.get("period")),
            "data_quality_flag": "可用",
        }
        row["data_quality_flag"] = row_quality(row)
        rows.append(row)
    return rows


def manifest_note(
    manifest: dict[str, dict[str, str]],
    filename: str,
    fallback_behavior: str,
) -> dict[str, str]:
    item = manifest.get(filename, {})
    return {
        "source_type": clean_value(item.get("source_type")),
        "source_name": clean_value(item.get("source_name")),
        "data_time": clean_value(item.get("data_time")),
        "period_or_basis": clean_value(item.get("period_or_basis")),
        "verification_status": clean_value(item.get("verification_status")),
        "missing_behavior": clean_value(item.get("missing_behavior") or fallback_behavior),
    }


def build_source_notes(peers: list[dict[str, str]], manifest: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    field_sources = {
        "peer_group": ("peer_universe.csv", "缺少股票池时停止 comps"),
        "theme_role": ("peer_universe.csv", "缺少主题角色时保留行并标记来源缺失"),
        "market_cap": ("market_snapshot.csv", "缺少行情时不做市值和估值排序"),
        "float_market_cap": ("market_snapshot.csv", "缺少行情时不做流动性排序"),
        "pe_ttm": ("market_snapshot.csv", "缺少估值时不做 PE 排序"),
        "pb": ("market_snapshot.csv", "缺少估值时不做 PB 排序"),
        "ps_ttm": ("market_snapshot.csv", "缺少估值时不做 PS 排序"),
        "return_5d": ("market_snapshot.csv#price_performance", "缺少短期表现时不展示 5 日收益率"),
        "return_20d": ("market_snapshot.csv#price_performance", "缺少短期表现时不展示 20 日收益率"),
        "revenue": ("financial_summary.csv", "缺少财务摘要时不做财务质量排序"),
        "net_profit": ("financial_summary.csv", "亏损或缺失时不做 PE 排序"),
        "roe": ("financial_summary.csv", "缺少 ROE 时不做盈利质量排序"),
    }
    for peer in peers:
        code = clean_value(peer.get("code"))
        for field_name, source_spec in field_sources.items():
            filename, fallback_behavior = source_spec
            note = manifest_note(manifest, filename, fallback_behavior)
            notes.append({"code": code, "field_name": field_name, **note})
    return notes


def build_exceptions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    exceptions: list[dict[str, str]] = []
    for row in rows:
        for field in MARKET_FIELDS + FINANCIAL_FIELDS:
            if row.get(field) == MISSING:
                exceptions.append(
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "exception_type": "missing_source",
                        "metric": field,
                        "observed_value": MISSING,
                        "action": "keep_with_flag",
                        "reason": f"{field} 缺少来源，保留公司但不用于相关排序。",
                    }
                )
        net_profit = to_number(row.get("net_profit", ""))
        if net_profit is not None and net_profit < 0:
            exceptions.append(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "exception_type": "negative_denominator",
                    "metric": "pe_ttm",
                    "observed_value": row.get("pe_ttm", MISSING),
                    "action": "exclude_from_statistics",
                    "reason": "净利润为负，PE 不具备同口径可比性。",
                }
            )
        pe = to_number(row.get("pe_ttm", ""))
        if pe is not None and pe > 100:
            exceptions.append(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "exception_type": "extreme_multiple",
                    "metric": "pe_ttm",
                    "observed_value": row.get("pe_ttm", MISSING),
                    "action": "keep_with_flag",
                    "reason": "PE 超过 100 倍，摘要中只作为异常估值观察。",
                }
            )
    return exceptions


def percentile(sorted_values: list[float], ratio: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * ratio
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def build_statistics(rows: list[dict[str, str]], exceptions: list[dict[str, str]]) -> list[dict[str, str]]:
    excluded_by_metric: dict[str, list[str]] = {}
    for item in exceptions:
        if item["action"] == "exclude_from_statistics":
            excluded_by_metric.setdefault(item["metric"], []).append(f"{item['code']}:{item['reason']}")

    stats: list[dict[str, str]] = []
    for metric in STAT_METRICS:
        values: list[tuple[str, float]] = []
        excluded = list(excluded_by_metric.get(metric, []))
        for row in rows:
            if any(reason.startswith(f"{row['code']}:") for reason in excluded):
                continue
            number = to_number(row.get(metric, ""))
            if number is None:
                excluded.append(f"{row['code']}:非数值或来源缺失")
                continue
            values.append((row["code"], number))
        numbers = sorted(value for _, value in values)
        if len(numbers) < 3:
            stats.append(
                {
                    "metric": metric,
                    "sample_size": str(len(numbers)),
                    "median": "样本不足，未计算分位数",
                    "average": "样本不足，未计算分位数",
                    "minimum": "样本不足，未计算分位数",
                    "maximum": "样本不足，未计算分位数",
                    "quartile_1": "样本不足，未计算分位数",
                    "quartile_3": "样本不足，未计算分位数",
                    "included_codes": ",".join(code for code, _ in values),
                    "excluded_codes": ";".join(excluded),
                }
            )
            continue
        stats.append(
            {
                "metric": metric,
                "sample_size": str(len(numbers)),
                "median": format_number(statistics.median(numbers)),
                "average": format_number(statistics.fmean(numbers)),
                "minimum": format_number(min(numbers)),
                "maximum": format_number(max(numbers)),
                "quartile_1": format_number(percentile(numbers, 0.25)),
                "quartile_3": format_number(percentile(numbers, 0.75)),
                "included_codes": ",".join(code for code, _ in values),
                "excluded_codes": ";".join(excluded),
            }
        )
    return stats


def build_data_gaps(
    pack_dir: Path,
    rows: list[dict[str, str]],
    manifest: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    expected_files = {
        "peer_universe.csv": "comps",
        "market_snapshot.csv": "ranking",
        "financial_summary.csv": "statistics",
        "source_manifest.json": "source_note",
    }
    for filename, required_for in expected_files.items():
        if not (pack_dir / filename).is_file():
            gaps.append(
                {
                    "code": "ALL",
                    "field_name": filename,
                    "required_for": required_for,
                    "gap_reason": "missing file",
                    "missing_behavior": "缺少文件时相关字段全部标记为来源缺失",
                }
            )
    for row in rows:
        for field in MARKET_FIELDS:
            if row.get(field) == MISSING:
                gaps.append(
                    {
                        "code": row["code"],
                        "field_name": field,
                        "required_for": "ranking",
                        "gap_reason": "missing value",
                        "missing_behavior": "不参与估值、流动性或市值排序",
                    }
                )
        for field in PRICE_PERFORMANCE_FIELDS:
            if row.get(field) == MISSING:
                gaps.append(
                    {
                        "code": row["code"],
                        "field_name": field,
                        "required_for": "display",
                        "gap_reason": "missing value",
                        "missing_behavior": "不展示短期表现，不参与估值或质量统计",
                    }
                )
        for field in FINANCIAL_FIELDS:
            if row.get(field) == MISSING:
                gaps.append(
                    {
                        "code": row["code"],
                        "field_name": field,
                        "required_for": "statistics",
                        "gap_reason": "missing value",
                        "missing_behavior": "不参与财务质量统计",
                    }
                )
    if not manifest:
        gaps.append(
            {
                "code": "ALL",
                "field_name": "source metadata",
                "required_for": "source_note",
                "gap_reason": "missing source_manifest.json",
                "missing_behavior": "所有来源说明标记为来源缺失",
            }
        )
    return gaps


def write_summary(
    path: Path,
    theme: str,
    rows: list[dict[str, str]],
    exceptions: list[dict[str, str]],
    stats: list[dict[str, str]],
    gaps: list[dict[str, str]],
) -> None:
    usable_rows = [row for row in rows if row["data_quality_flag"] == "可用"]
    unusable_metrics = sorted({gap["field_name"] for gap in gaps if gap["code"] != "ALL"})
    exception_lines = [
        f"- {item['code']} {item['name']}：{item['metric']} {item['reason']}"
        for item in exceptions[:20]
    ]
    stat_lines = [
        f"- {item['metric']}：样本 {item['sample_size']}，中位数 {item['median']}，排除 {item['excluded_codes'] or '无'}。"
        for item in stats
    ]
    lines = [
        f"# {theme} comps artifact summary",
        "",
        "## 可用数据",
        f"- 主表包含 {len(rows)} 家公司，其中 {len(usable_rows)} 家具备核心市值、估值和财务字段。",
        "- 行情、估值和财务字段均来自 research-pack 本地文件；脚本未联网补数。",
        "",
        "## 不可用于排序的数据",
        f"- 不可用于排序或统计的字段：{', '.join(unusable_metrics) if unusable_metrics else '无'}。",
        "- `来源缺失`、`口径不可比`、`不适用` 字段不得用于排名结论。",
        "",
        "## 异常值和不可比项",
    ]
    lines.extend(exception_lines or ["- 无异常值或不可比项。"])
    lines.extend(
        [
            "",
            "## 统计分布",
        ]
    )
    lines.extend(stat_lines)
    lines.extend(
        [
            "",
            "## 对 idea generation 的交接",
            "- 只把有来源和统计样本支持的估值、流动性、盈利质量观察交给 idea generation。",
            "- `return_5d` 和 `return_20d` 只作为短期表现展示口径，不进入估值或质量统计。",
            "- 亏损公司、极端估值和缺少来源的字段必须作为风险或待验证问题传递。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    pack_dir = Path(args.research_pack)
    output_dir = Path(args.output_dir) if args.output_dir else stage_dir(args.theme, "comps")
    output_dir.mkdir(parents=True, exist_ok=True)

    peers = read_csv(pack_dir / "peer_universe.csv")
    if not peers:
        raise SystemExit(f"missing or empty peer_universe.csv in {pack_dir}")

    market_by_code = index_by_code(read_csv(pack_dir / "market_snapshot.csv"))
    financial_by_code = index_by_code(read_csv(pack_dir / "financial_summary.csv"))
    manifest = read_source_manifest(pack_dir)

    main_rows = build_comps_main(peers, market_by_code, financial_by_code)
    source_notes = build_source_notes(peers, manifest)
    exceptions = build_exceptions(main_rows)
    stats = build_statistics(main_rows, exceptions)
    gaps = build_data_gaps(pack_dir, main_rows, manifest)

    write_csv(output_dir / "comps_main.csv", main_rows, MAIN_FIELDS)
    write_csv(output_dir / "comps_source_notes.csv", source_notes, SOURCE_NOTE_FIELDS)
    write_csv(output_dir / "comps_exceptions.csv", exceptions, EXCEPTION_FIELDS)
    write_csv(output_dir / "comps_statistics.csv", stats, STAT_FIELDS)
    write_csv(output_dir / "comps_data_gaps.csv", gaps, DATA_GAP_FIELDS)
    write_summary(output_dir / "comps_summary.md", args.theme, main_rows, exceptions, stats, gaps)

    print(f"wrote comps artifacts: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
