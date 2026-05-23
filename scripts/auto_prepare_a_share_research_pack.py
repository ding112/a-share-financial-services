#!/usr/bin/env python3
"""Automatically prepare a local A-share research-pack."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FETCHER = ROOT / "scripts/fetch_a_share_public_data.py"
EVENTS_FETCHER = ROOT / "scripts/fetch_a_share_events_risks.py"
MARKET_CONTEXT_FETCHER = ROOT / "scripts/fetch_a_share_market_context.py"
MACRO_CONTEXT_FETCHER = ROOT / "scripts/fetch_a_share_macro_context.py"
COMPANY_DETAILS_FETCHER = ROOT / "scripts/fetch_a_share_company_details.py"
NORTHBOUND_MARGIN_FETCHER = ROOT / "scripts/fetch_a_share_northbound_margin.py"
BOARD_SECTOR_FETCHER = ROOT / "scripts/fetch_a_share_board_sector.py"
FUND_HOLDINGS_FETCHER = ROOT / "scripts/fetch_a_share_fund_holdings.py"
INDEX_VALUATION_FETCHER = ROOT / "scripts/fetch_a_share_index_valuation.py"

PEER_COLUMNS = [
    "code",
    "name",
    "exchange",
    "board",
    "peer_group",
    "theme_role",
    "exposure_summary",
    "exposure_source_ref",
]

CANDIDATE_COLUMNS = PEER_COLUMNS + [
    "candidate_source",
    "candidate_board",
    "selection_metric",
    "selection_value",
    "verification_status",
]

AUTO_OUTPUTS = [
    "candidate_peer_universe.csv",
    "peer_universe.csv",
    "market_snapshot.csv",
    "financial_summary.csv",
    "events_and_risks.md",
    "market_context_fund_flow.csv",
    "market_context_board_changes.csv",
    "market_context_limit_up.csv",
    "market_context_stock_fund_flow.csv",
    "macro_context.csv",
    "company_details.csv",
    "northbound_flow.csv",
    "northbound_holdings.csv",
    "margin_trading.csv",
    "board_sector_context.csv",
    "fund_heavy_stocks.csv",
    "etf_list.csv",
    "index_valuation.csv",
    "market_pe_pb.csv",
    "index_spot.csv",
    "source_manifest.json",
    "fetch_errors.csv",
    "auto_prepare_manifest.json",
]

FIXTURE_CANDIDATES = [
    ("300750.SZ", "宁德时代", "电池", "核心成分", 1840000000, 960000000000),
    ("002594.SZ", "比亚迪", "整车", "核心成分", 1560000000, 780000000000),
    ("601012.SH", "隆基绿能", "光伏设备", "核心成分", 920000000, 160000000000),
    ("300124.SZ", "汇川技术", "自动化", "核心成分", 880000000, 170000000000),
    ("002050.SZ", "三花智控", "零部件", "核心成分", 760000000, 98000000000),
    ("688017.SH", "绿的谐波", "机器人零部件", "核心成分", 520000000, 21000000000),
    ("002472.SZ", "双环传动", "传动部件", "核心成分", 510000000, 26000000000),
    ("002747.SZ", "埃斯顿", "机器人本体", "核心成分", 480000000, 18000000000),
    ("002236.SZ", "大华股份", "机器视觉", "核心成分", 460000000, 65000000000),
    ("300024.SZ", "机器人", "机器人本体", "核心成分", 430000000, 19000000000),
    ("688160.SH", "步科股份", "控制系统", "核心成分", 320000000, 8500000000),
    ("688320.SH", "禾川科技", "伺服系统", "核心成分", 300000000, 7600000000),
    ("002031.SZ", "巨轮智能", "机器人设备", "核心成分", 280000000, 11000000000),
    ("603728.SH", "鸣志电器", "电机控制", "核心成分", 260000000, 21000000000),
    ("002527.SZ", "新时达", "控制系统", "核心成分", 240000000, 9800000000),
    ("000000.SZ", "*ST示例", "风险样本", "剔除样本", 999999999, 999999999),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", required=True, help="Chinese A-share theme or sector.")
    parser.add_argument("--output-dir", required=True, help="Directory for the research-pack.")
    parser.add_argument("--as-of", required=True, help="Access date or quote timestamp.")
    parser.add_argument("--peer-universe", help="Optional existing peer_universe.csv.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite auto-generated research-pack files if the output directory exists.",
    )
    parser.add_argument(
        "--universe-source",
        choices=["akshare", "fixture"],
        default="akshare",
        help="Source for theme-to-universe generation when --peer-universe is absent.",
    )
    parser.add_argument(
        "--market-source",
        choices=["tencent", "eastmoney", "fixture"],
        default="tencent",
        help="Market data source passed to fetch_a_share_public_data.py.",
    )
    parser.add_argument(
        "--financial-source",
        choices=["eastmoney", "akshare", "fixture"],
        default="eastmoney",
        help="Financial data source passed to fetch_a_share_public_data.py.",
    )
    parser.add_argument(
        "--max-peers",
        type=int,
        default=15,
        help="Maximum companies to include in peer_universe.csv.",
    )
    return parser.parse_args()


def normalize_a_share_code(raw_code: str) -> str:
    code = raw_code.strip().upper()
    if "." in code:
        symbol, exchange = code.split(".", 1)
        return f"{symbol.zfill(6)}.{exchange}"
    symbol = code.zfill(6)
    if symbol.startswith(("600", "601", "603", "605", "688", "689")):
        return f"{symbol}.SH"
    if symbol.startswith(
        (
            "430",
            "830",
            "831",
            "832",
            "833",
            "834",
            "835",
            "836",
            "837",
            "838",
            "839",
            "870",
            "871",
            "872",
            "873",
            "920",
        )
    ):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"


def infer_exchange(code: str) -> str:
    normalized = normalize_a_share_code(code)
    return normalized.rsplit(".", 1)[1]


def infer_board(code: str) -> str:
    symbol = normalize_a_share_code(code).split(".", 1)[0]
    if symbol.startswith("688"):
        return "科创板"
    if symbol.startswith(("300", "301")):
        return "创业板"
    if symbol.startswith(
        (
            "430",
            "830",
            "831",
            "832",
            "833",
            "834",
            "835",
            "836",
            "837",
            "838",
            "839",
            "870",
            "871",
            "872",
            "873",
            "920",
        )
    ):
        return "北交所"
    return "主板"


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_一二三四五六七八九十" else "-" for char in value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def complete_research_pack(output_dir: Path) -> bool:
    return all((output_dir / filename).is_file() for filename in AUTO_OUTPUTS)


def selected_value(row: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return ""


def to_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    cleaned = str(value).replace(",", "").replace("%", "").strip()
    if cleaned in {"-", "--", "nan", "None"}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def is_risk_name(name: str) -> bool:
    upper = name.upper()
    return "ST" in upper or "退" in name


def fixture_candidates(theme: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, name, group, role, amount, market_cap in FIXTURE_CANDIDATES:
        rows.append(
            {
                "code": code,
                "name": name,
                "source_board": f"{theme} fixture 概念板块",
                "candidate_source": "fixture",
                "candidate_board": f"{theme} fixture 概念板块",
                "peer_group": group,
                "theme_role": role,
                "amount": amount,
                "market_cap": market_cap,
            }
        )
    return rows


def load_akshare():
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "自动股票池生成需要 AkShare。请先在当前目录创建 .venv 并安装 requirements.txt。"
        ) from exc
    return ak


def board_name(row: dict[str, Any]) -> str:
    return str(selected_value(row, ["板块名称", "name", "名称", "行业名称", "概念名称"]))


def match_score(theme: str, board: str) -> int:
    if not board:
        return 0
    if theme == board:
        return 1000
    if theme in board or board in theme:
        return 500 + min(len(theme), len(board))
    return len(set(theme) & set(board))


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


def fetch_akshare_candidates(theme: str) -> list[dict[str, Any]]:
    ak = load_akshare()
    board_specs = [
        ("akshare_concept_board", ak.stock_board_concept_name_em, ak.stock_board_concept_cons_em),
        ("akshare_industry_board", ak.stock_board_industry_name_em, ak.stock_board_industry_cons_em),
    ]
    errors: list[str] = []
    best: tuple[int, str, str, Any] | None = None
    for source_name, list_func, constituents_func in board_specs:
        try:
            boards = dataframe_to_records(list_func())
        except Exception as exc:
            errors.append(f"{source_name} list failed: {exc}")
            continue
        for board in boards:
            name = board_name(board)
            score = match_score(theme, name)
            if best is None or score > best[0]:
                best = (score, source_name, name, constituents_func)

    if best is None or best[0] <= 0:
        detail = "; ".join(errors) if errors else "no matching public board"
        raise RuntimeError(f"无法从 AkShare 公开板块匹配主题 `{theme}`: {detail}")

    _, source_name, matched_board, constituents_func = best
    try:
        records = dataframe_to_records(constituents_func(symbol=matched_board))
    except Exception as exc:
        raise RuntimeError(f"AkShare board constituents failed for `{matched_board}`: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for record in records:
        code = selected_value(record, ["代码", "证券代码", "股票代码", "code"])
        name = selected_value(record, ["名称", "股票简称", "简称", "name"])
        if not code or not name:
            continue
        rows.append(
            {
                "code": normalize_a_share_code(str(code)),
                "name": str(name),
                "candidate_source": source_name,
                "candidate_board": matched_board,
                "source_board": matched_board,
                "peer_group": matched_board,
                "theme_role": "公开板块成分",
                "amount": selected_value(record, ["成交额", "成交额(元)", "成交额-元", "amount"]),
                "market_cap": selected_value(record, ["总市值", "总市值-元", "流通市值", "market_cap"]),
            }
        )
    if not rows:
        raise RuntimeError(f"AkShare board `{matched_board}` returned no usable A-share candidates")
    return rows


def load_candidates(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    if args.peer_universe:
        rows = read_csv(Path(args.peer_universe))
        return [
            {
                **row,
                "code": normalize_a_share_code(row.get("code", "")),
                "name": row.get("name", ""),
                "candidate_source": "user_provided",
                "candidate_board": row.get("peer_group") or args.theme,
                "source_board": row.get("peer_group") or args.theme,
                "peer_group": row.get("peer_group") or args.theme,
                "theme_role": row.get("theme_role") or "待验证",
                "amount": 0,
                "market_cap": 0,
            }
            for row in rows
        ], "user_provided"
    if args.universe_source == "fixture":
        return fixture_candidates(args.theme), "fixture"
    return fetch_akshare_candidates(args.theme), "akshare"


def candidate_row(candidate: dict[str, Any], theme: str) -> dict[str, str]:
    code = normalize_a_share_code(str(candidate.get("code", "")))
    source = str(candidate.get("candidate_source", "public_concept_board"))
    board = str(candidate.get("candidate_board") or candidate.get("source_board") or theme)
    metric, value = selection_metric(candidate)
    is_user_provided = source == "user_provided"
    exposure_summary = str(
        candidate.get("exposure_summary") or "公开概念/板块成分识别，业务暴露待验证"
    )
    exposure_source_ref = str(
        candidate.get("exposure_source_ref") or f"public_concept_board:{source}:{board}"
    )
    return {
        "code": code,
        "name": str(candidate.get("name", "")),
        "exchange": infer_exchange(code),
        "board": infer_board(code),
        "peer_group": str(candidate.get("peer_group") or board or theme),
        "theme_role": str(candidate.get("theme_role") or "待验证") if is_user_provided else "待验证",
        "exposure_summary": exposure_summary if is_user_provided else "公开概念/板块成分识别，业务暴露待验证",
        "exposure_source_ref": exposure_source_ref if is_user_provided else f"public_concept_board:{source}:{board}",
        "candidate_source": source,
        "candidate_board": board,
        "selection_metric": metric,
        "selection_value": str(value),
        "verification_status": "待验证",
    }


def selection_metric(candidate: dict[str, Any]) -> tuple[str, float]:
    amount = to_number(candidate.get("amount"))
    if amount:
        return "amount", amount
    market_cap = to_number(candidate.get("market_cap"))
    if market_cap:
        return "market_cap", market_cap
    return "source_order", 0.0


def build_peer_universe(
    candidates: list[dict[str, Any]],
    theme: str,
    max_peers: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    normalized = [candidate_row(candidate, theme) for candidate in candidates]
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in normalized:
        if not row["code"] or row["code"] in seen:
            continue
        seen.add(row["code"])
        deduped.append(row)

    filtered = [row for row in deduped if not is_risk_name(row["name"])]

    def sort_key(row: dict[str, str]) -> tuple[int, float]:
        metric = row["selection_metric"]
        priority = 2 if metric == "amount" else 1 if metric == "market_cap" else 0
        return (priority, to_number(row["selection_value"]))

    sorted_rows = sorted(filtered, key=sort_key, reverse=True)
    selected = sorted_rows[:max(1, max_peers)]
    peer_rows = [{column: row[column] for column in PEER_COLUMNS} for row in selected]
    selection = {
        "candidate_count": len(normalized),
        "deduped_count": len(deduped),
        "filtered_risk_count": len(deduped) - len(filtered),
        "selected_count": len(selected),
        "max_peers": max_peers,
        "selection_rule": "amount desc, then market_cap desc, then source order; ST and delisting-risk names excluded",
        "universe_size_warning": len(selected) < 8,
    }
    return normalized, peer_rows, selection


def write_auto_prepare_manifest(
    path: Path,
    args: argparse.Namespace,
    source: str,
    selection: dict[str, Any],
) -> None:
    payload = {
        "theme": args.theme,
        "as_of": args.as_of,
        "inputs": {
            "peer_universe": args.peer_universe,
            "universe_source": source,
            "market_source": args.market_source,
            "financial_source": args.financial_source,
        },
        "outputs": {filename: filename for filename in AUTO_OUTPUTS},
        "selection": selection,
        "notes": [
            "自动股票池来自公开概念/板块成分或用户提供股票池。",
            "概念/板块成分只作线索，业务暴露必须标记为待验证。",
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_public_data_fetcher(args: argparse.Namespace, peer_path: Path, output_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        peer_input = Path(tmp) / "peer_universe.csv"
        shutil.copyfile(peer_path, peer_input)
        command = [
            sys.executable,
            str(FETCHER),
            "--peer-universe",
            str(peer_input),
            "--output-dir",
            str(output_dir),
            "--as-of",
            args.as_of,
            "--market-source",
            args.market_source,
            "--financial-source",
            args.financial_source,
        ]
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"fetch_a_share_public_data.py exited {result.returncode}: {result.stderr.strip()}"
        )


def run_events_risks_fetcher(args: argparse.Namespace, peer_path: Path, output_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        peer_input = Path(tmp) / "peer_universe.csv"
        shutil.copyfile(peer_path, peer_input)
        command = [
            sys.executable,
            str(EVENTS_FETCHER),
            "--peer-universe",
            str(peer_input),
            "--output-dir",
            str(output_dir),
            "--as-of",
            args.as_of,
        ]
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"warning: fetch_a_share_events_risks.py exited {result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )


def _run_optional_fetcher(name: str, command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"warning: {name} exited {result.returncode}: {result.stderr.strip()}", file=sys.stderr)


def run_market_context_fetcher(args: argparse.Namespace, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_market_context.py",
        [sys.executable, str(MARKET_CONTEXT_FETCHER), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def run_macro_context_fetcher(args: argparse.Namespace, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_macro_context.py",
        [sys.executable, str(MACRO_CONTEXT_FETCHER), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def run_company_details_fetcher(args: argparse.Namespace, peer_path: Path, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_company_details.py",
        [sys.executable, str(COMPANY_DETAILS_FETCHER), "--peer-universe", str(peer_path), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def run_northbound_margin_fetcher(args: argparse.Namespace, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_northbound_margin.py",
        [sys.executable, str(NORTHBOUND_MARGIN_FETCHER), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def run_board_sector_fetcher(args: argparse.Namespace, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_board_sector.py",
        [sys.executable, str(BOARD_SECTOR_FETCHER), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def run_fund_holdings_fetcher(args: argparse.Namespace, peer_path: Path, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_fund_holdings.py",
        [sys.executable, str(FUND_HOLDINGS_FETCHER), "--peer-universe", str(peer_path), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def run_index_valuation_fetcher(args: argparse.Namespace, output_dir: Path) -> None:
    _run_optional_fetcher(
        "fetch_a_share_index_valuation.py",
        [sys.executable, str(INDEX_VALUATION_FETCHER), "--output-dir", str(output_dir), "--as-of", args.as_of],
    )


def patch_source_manifest(
    output_dir: Path,
    args: argparse.Namespace,
    source: str,
) -> None:
    manifest_path = output_dir / "source_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    for item in files:
        if item.get("file") == "peer_universe.csv":
            item["source_type"] = "user_provided" if source == "user_provided" else "public_market_data"
            item["source_name"] = (
                "用户提供股票池" if source == "user_provided" else f"{source} 公开概念/板块成分"
            )
            item["data_time"] = args.as_of
            item["period_or_basis"] = "用户提供" if source == "user_provided" else "公开板块成分"
            item["verification_status"] = "user_provided" if source == "user_provided" else "待验证"
            item["missing_behavior"] = "缺少股票池时停止 comps 和 idea shortlist"
    files.append(
        {
            "file": "candidate_peer_universe.csv",
            "source_type": "user_provided" if source == "user_provided" else "public_market_data",
            "source_name": (
                "用户提供股票池候选" if source == "user_provided" else f"{source} 公开概念/板块候选"
            ),
            "data_time": args.as_of,
            "period_or_basis": "候选股票池",
            "verification_status": "user_provided" if source == "user_provided" else "待验证",
            "missing_behavior": "缺失时不能回溯自动候选来源",
        }
    )
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_writable_output(output_dir: Path, force: bool) -> None:
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        return
    if complete_research_pack(output_dir) and not force:
        print(f"reusing existing research-pack: {output_dir}")
        raise SystemExit(0)
    if not force and any(output_dir.iterdir()):
        raise RuntimeError(f"incomplete research-pack exists at {output_dir}; rerun with --force")
    output_dir.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    if args.max_peers < 1:
        raise SystemExit("--max-peers must be positive")
    output_dir = Path(args.output_dir)
    ensure_writable_output(output_dir, args.force)

    candidates, source = load_candidates(args)
    candidate_rows, peer_rows, selection = build_peer_universe(candidates, args.theme, args.max_peers)
    if not peer_rows:
        raise SystemExit("无法生成 peer_universe.csv：候选股票池为空")

    write_csv(output_dir / "candidate_peer_universe.csv", candidate_rows, CANDIDATE_COLUMNS)
    peer_path = output_dir / "peer_universe.csv"
    write_csv(peer_path, peer_rows, PEER_COLUMNS)
    run_public_data_fetcher(args, peer_path, output_dir)
    run_events_risks_fetcher(args, peer_path, output_dir)
    run_market_context_fetcher(args, output_dir)
    run_macro_context_fetcher(args, output_dir)
    run_company_details_fetcher(args, peer_path, output_dir)
    run_northbound_margin_fetcher(args, output_dir)
    run_board_sector_fetcher(args, output_dir)
    run_fund_holdings_fetcher(args, peer_path, output_dir)
    run_index_valuation_fetcher(args, output_dir)
    patch_source_manifest(output_dir, args, source)
    write_auto_prepare_manifest(output_dir / "auto_prepare_manifest.json", args, source, selection)

    print(f"wrote auto research-pack: {output_dir}")
    if selection["universe_size_warning"]:
        print("warning: selected fewer than 8 peers; analyst review required", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
