"""共享 A 股证券代码与股票池解析。"""

from __future__ import annotations

import csv
import re
from pathlib import Path

MISSING = "来源缺失"
BJ_PREFIXES = (
    "430", "830", "831", "832", "833", "834", "835", "836", "837",
    "838", "839", "870", "871", "872", "873", "920",
)


def infer_exchange(symbol: str) -> str | None:
    if symbol.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if symbol.startswith(BJ_PREFIXES):
        return "BJ"
    if symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ"
    return None


def normalize_a_share_code(raw_code: str) -> str:
    value = raw_code.strip().upper()
    match = re.fullmatch(r"(\d{1,6})(?:\.(SH|SZ|BJ))?", value)
    if not match:
        raise ValueError(f"不支持的 A 股代码: {raw_code!r}")
    symbol = match.group(1).zfill(6)
    inferred = infer_exchange(symbol)
    supplied = match.group(2)
    if inferred is None or (supplied and supplied != inferred):
        raise ValueError(f"不支持的 A 股代码: {raw_code!r}")
    return f"{symbol}.{inferred}"


def read_peer_universe(path: Path) -> tuple[list[dict[str, str]], list[tuple[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "code" not in reader.fieldnames:
            raise ValueError(f"股票池需要 code 列: {path}")
        raw_rows = list(reader)

    peers: list[dict[str, str]] = []
    errors: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in raw_rows:
        raw_code = str(row.get("code") or "").strip()
        try:
            code = normalize_a_share_code(raw_code)
        except ValueError as exc:
            errors.append((raw_code or MISSING, str(exc)))
            continue
        if code in seen:
            continue
        seen.add(code)
        peers.append({"code": code, "name": str(row.get("name") or "").strip()})
    return peers, errors
