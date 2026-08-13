#!/usr/bin/env python3
"""为 A 股 research-pack 抓取东方财富大宗交易与股东户数事实。

东方财富端点与字段映射参考 Apache-2.0 项目 ``a-stock-data`` 和 AkShare
接口目录；本实现使用标准库重新实现完整分页，并遵循本项目的研究截止日、
来源、缺失和错误契约。大宗交易事实不构成资金意图或价格方向判断。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from collections.abc import Iterable, Iterator
from typing import Any, Callable

MISSING = "来源缺失"
BLOCK_SOURCE_NAME = "东方财富大宗交易"
BLOCK_SOURCE_KEY = "eastmoney_block_trade"
SHAREHOLDER_SOURCE_NAME = "东方财富股东户数"
SHAREHOLDER_SOURCE_KEY = "eastmoney_shareholder_count"
DATA_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
USER_AGENT = "Mozilla/5.0 a-share-market-researcher/0.1"
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_RETRY_ATTEMPTS = 3
REQUEST_RETRY_DELAY_SECONDS = 0.6
REQUEST_INTERVAL_SECONDS = 1.1
PAGE_SIZE = 500
PERCENT_TOLERANCE = Decimal("0.02")

BLOCK_COLUMNS = [
    "block_trade_id",
    "security_code",
    "security_name",
    "trade_date",
    "close_price_cny",
    "deal_price_cny",
    "deal_volume_shares",
    "deal_amount_cny",
    "premium_discount_pct",
    "premium_discount_pct_basis",
    "buyer_name",
    "seller_name",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]
SHAREHOLDER_COLUMNS = [
    "shareholder_snapshot_id",
    "security_code",
    "security_name",
    "statistical_end_date",
    "announcement_date",
    "holder_count",
    "previous_holder_count",
    "holder_count_change",
    "holder_count_change_basis",
    "holder_count_change_pct",
    "holder_count_change_pct_basis",
    "average_holding_shares",
    "average_holding_market_value_cny",
    "total_market_cap_cny",
    "total_shares",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]
ERROR_COLUMNS = ["code", "source", "stage", "error"]
BLOCK_FIELDS = (
    "TRADE_DATE,SECURITY_CODE,SECURITY_NAME_ABBR,CLOSE_PRICE,DEAL_PRICE,"
    "PREMIUM_RATIO,DEAL_VOLUME,DEAL_AMT,BUYER_NAME,SELLER_NAME"
)
SHAREHOLDER_FIELDS = (
    "SECURITY_CODE,SECURITY_NAME_ABBR,END_DATE,HOLD_NOTICE_DATE,HOLDER_NUM,"
    "PRE_HOLDER_NUM,HOLDER_NUM_CHANGE,HOLDER_NUM_RATIO,AVG_HOLD_NUM,"
    "AVG_MARKET_CAP,TOTAL_MARKET_CAP,TOTAL_A_SHARES"
)
BJ_PREFIXES = (
    "430", "830", "831", "832", "833", "834", "835", "836", "837",
    "838", "839", "870", "871", "872", "873", "920",
)

_last_request_at = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="包含 A 股股票池的 CSV。")
    parser.add_argument("--output-dir", required=True, help="research-pack 输出目录。")
    parser.add_argument("--as-of", required=True, help="研究截止日，例如 2026-08-13。")
    parser.add_argument(
        "--block-trade-lookback-days",
        type=int,
        default=365,
        help="截至 as-of 的大宗交易回溯天数，默认 365。",
    )
    parser.add_argument(
        "--block-trade-limit-per-security",
        type=int,
        default=50,
        help="每个证券最多保留的大宗交易笔数，默认 50。",
    )
    parser.add_argument(
        "--shareholder-lookback-days",
        type=int,
        default=730,
        help="截至 as-of 的股东户数统计截止日回溯天数，默认 730。",
    )
    parser.add_argument(
        "--shareholder-limit-per-security",
        type=int,
        default=8,
        help="每个证券最多保留的股东户数可见快照数，默认 8。",
    )
    parser.add_argument(
        "--source",
        choices=["eastmoney", "fixture"],
        default="eastmoney",
        help="大宗交易来源；fixture 仅用于离线检查。",
    )
    parser.add_argument(
        "--fixture-scenario",
        choices=[
            "success",
            "no-data",
            "partial-failure",
            "all-failure",
            "invalid-row",
            "derived-conflict",
            "as-of-pagination",
            "duplicate-block-trades",
            "block-trade-all-failure",
            "shareholder-all-failure",
            "malformed-response",
            "all-invalid-records",
            "filtered-plus-invalid",
            "insufficient-derived",
            "early-stop-before-failure",
        ],
        default="success",
        help="fixture 离线场景。",
    )
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_as_of(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


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
        raise ValueError(f"unsupported A-share code: {raw_code!r}")
    symbol = match.group(1).zfill(6)
    inferred = infer_exchange(symbol)
    supplied = match.group(2)
    if inferred is None or (supplied and supplied != inferred):
        raise ValueError(f"unsupported A-share code: {raw_code!r}")
    return f"{symbol}.{inferred}"


def read_peer_universe(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "code" not in reader.fieldnames:
            raise ValueError(f"peer universe requires code column: {path}")
        raw_rows = list(reader)
    peers: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in raw_rows:
        raw_code = str(row.get("code") or "").strip()
        try:
            code = normalize_a_share_code(raw_code)
        except ValueError as exc:
            errors.append(error_row(raw_code or MISSING, BLOCK_SOURCE_KEY, "market_activity_input", str(exc)))
            continue
        if code in seen:
            continue
        seen.add(code)
        peers.append({"code": code, "name": str(row.get("name") or "").strip()})
    if not peers:
        raise ValueError(f"peer universe contains no valid A-share code: {path}")
    return peers, errors


def error_row(code: str, source: str, stage: str, error: str) -> dict[str, str]:
    return {"code": code, "source": source, "stage": stage, "error": error}


def _throttle_request() -> None:
    global _last_request_at
    wait_seconds = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def request_json(params: dict[str, str]) -> dict[str, Any]:
    global _last_request_at
    url = f"{DATA_API}?{urllib.parse.urlencode(params)}"
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRY_ATTEMPTS):
        _throttle_request()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://data.eastmoney.com/",
                "Accept": "application/json, text/plain, */*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Eastmoney response must be a JSON object")
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in retryable_statuses:
                raise
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
        finally:
            _last_request_at = time.monotonic()
        if attempt + 1 < REQUEST_RETRY_ATTEMPTS:
            time.sleep(REQUEST_RETRY_DELAY_SECONDS * (attempt + 1))
    raise RuntimeError(f"Eastmoney request failed after retries: {last_error}")


def validate_response(payload: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    if payload.get("success") is not True:
        raise ValueError(f"Eastmoney response unsuccessful: {payload.get('message') or payload.get('code')}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("Eastmoney response result must be an object")
    pages = result.get("pages", 0)
    data = result.get("data")
    if not isinstance(pages, int) or pages < 0:
        raise ValueError("Eastmoney response pages must be a non-negative integer")
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError("Eastmoney response data must be a list of objects")
    return pages, data


def fetch_eastmoney_report_pages(params: dict[str, str]) -> Iterator[list[dict[str, Any]]]:
    page = 1
    total_pages = 1
    while page <= total_pages:
        page_params = {
            **params,
            "pageSize": str(PAGE_SIZE),
            "pageNumber": str(page),
            "source": "WEB",
            "client": "WEB",
        }
        total_pages, data = validate_response(request_json(page_params))
        yield data
        page += 1


def fetch_eastmoney_pages(
    peer: dict[str, str], begin: dt.date, end: dt.date
) -> Iterator[list[dict[str, Any]]]:
    symbol = peer["code"].split(".", 1)[0]
    return fetch_eastmoney_report_pages(
        {
            "reportName": "RPT_DATA_BLOCKTRADE",
            "columns": BLOCK_FIELDS,
            "filter": (
                f'(SECURITY_TYPE_WEB="1")(SECURITY_CODE="{symbol}")'
                f"(TRADE_DATE>='{begin.isoformat()}')(TRADE_DATE<='{end.isoformat()}')"
            ),
            "sortColumns": "TRADE_DATE,SECURITY_CODE",
            "sortTypes": "-1,1",
        }
    )


def fetch_shareholder_eastmoney_pages(
    peer: dict[str, str],
) -> Iterator[list[dict[str, Any]]]:
    """完整分页读取个股历史详情；可见性过滤在本地统一执行。"""
    symbol = peer["code"].split(".", 1)[0]
    return fetch_eastmoney_report_pages(
        {
            "reportName": "RPT_HOLDERNUM_DET",
            "columns": SHAREHOLDER_FIELDS,
            "filter": f'(SECURITY_CODE="{symbol}")',
            "sortColumns": "END_DATE,HOLD_NOTICE_DATE",
            "sortTypes": "-1,-1",
        }
    )


def fixture_record(peer: dict[str, str], trade_date: dt.date, *, suffix: int = 0) -> dict[str, Any]:
    symbol = peer["code"].split(".", 1)[0]
    if suffix == 0:
        return {
            "TRADE_DATE": trade_date.isoformat(),
            "SECURITY_CODE": symbol,
            "SECURITY_NAME_ABBR": peer.get("name") or "fixture 样本",
            "CLOSE_PRICE": 10,
            "DEAL_PRICE": 10.5,
            "PREMIUM_RATIO": 5,
            "DEAL_VOLUME": 12000,
            "DEAL_AMT": 126000,
            "BUYER_NAME": "fixture 买方",
            "SELLER_NAME": "fixture 卖方",
        }
    return {
        "TRADE_DATE": (trade_date - dt.timedelta(days=suffix)).isoformat(),
        "SECURITY_CODE": symbol,
        "SECURITY_NAME_ABBR": peer.get("name") or "fixture 样本",
        "CLOSE_PRICE": 8,
        "DEAL_PRICE": 8.4,
        "PREMIUM_RATIO": None,
        "DEAL_VOLUME": 1000 + suffix,
        "DEAL_AMT": Decimal("8.4") * Decimal(1000 + suffix),
        "BUYER_NAME": None,
        "SELLER_NAME": None,
    }


def page_then_failure(
    page: list[dict[str, Any]], message: str
) -> Iterator[list[dict[str, Any]]]:
    yield page
    raise RuntimeError(message)


def fixture_pages(
    peer: dict[str, str], end: dt.date, scenario: str, peer_index: int
) -> Iterable[list[dict[str, Any]]]:
    if scenario == "malformed-response":
        _, data = validate_response({"success": True, "result": None})
        return [data]
    if scenario in {"all-failure", "block-trade-all-failure"} or (
        scenario == "partial-failure" and peer_index == 0
    ):
        raise RuntimeError("fixture block trade failure")
    if scenario == "no-data":
        return [[]]
    if scenario == "early-stop-before-failure":
        return page_then_failure(
            [fixture_record(peer, end - dt.timedelta(days=1))],
            "fixture unexpected block trade next-page request",
        )
    if scenario == "as-of-pagination":
        return [
            [fixture_record(peer, end + dt.timedelta(days=1))],
            [fixture_record(peer, end - dt.timedelta(days=1))],
        ]
    if scenario == "duplicate-block-trades":
        record = fixture_record(peer, end - dt.timedelta(days=1))
        return [[dict(record), dict(record)]]
    if scenario == "invalid-row":
        bad = fixture_record(peer, end)
        bad["DEAL_PRICE"] = None
        return [[bad, fixture_record(peer, end - dt.timedelta(days=1))]]
    if scenario == "all-invalid-records":
        bad = fixture_record(peer, end)
        bad["DEAL_PRICE"] = None
        return [[bad]]
    if scenario == "filtered-plus-invalid":
        bad = fixture_record(peer, end)
        bad["DEAL_PRICE"] = None
        return [[fixture_record(peer, end + dt.timedelta(days=1)), bad]]
    if scenario == "insufficient-derived":
        record = fixture_record(peer, end - dt.timedelta(days=1))
        record["CLOSE_PRICE"] = None
        record["PREMIUM_RATIO"] = None
        return [[record]]
    if scenario == "derived-conflict":
        record = fixture_record(peer, end - dt.timedelta(days=1))
        record["PREMIUM_RATIO"] = 99
        return [[record]]
    return [[fixture_record(peer, end - dt.timedelta(days=1)), fixture_record(peer, end, suffix=2)]]


def fixture_shareholder_record(
    peer: dict[str, str],
    statistical_end_date: dt.date,
    announcement_date: dt.date,
    *,
    calculated: bool = False,
) -> dict[str, Any]:
    symbol = peer["code"].split(".", 1)[0]
    if not calculated:
        return {
            "SECURITY_CODE": symbol,
            "SECURITY_NAME_ABBR": peer.get("name") or "fixture 样本",
            "END_DATE": statistical_end_date.isoformat(),
            "HOLD_NOTICE_DATE": announcement_date.isoformat(),
            "HOLDER_NUM": 10000,
            "PRE_HOLDER_NUM": 10100,
            "HOLDER_NUM_CHANGE": -100,
            "HOLDER_NUM_RATIO": Decimal("-0.9901"),
            "AVG_HOLD_NUM": Decimal("19853.4"),
            "AVG_MARKET_CAP": Decimal("79215.075"),
            "TOTAL_MARKET_CAP": Decimal("38799544166.666"),
            "TOTAL_A_SHARES": 9724196533,
        }
    return {
        "SECURITY_CODE": symbol,
        "SECURITY_NAME_ABBR": peer.get("name") or "fixture 样本",
        "END_DATE": statistical_end_date.isoformat(),
        "HOLD_NOTICE_DATE": announcement_date.isoformat(),
        "HOLDER_NUM": 9000,
        "PRE_HOLDER_NUM": 10000,
        "HOLDER_NUM_CHANGE": None,
        "HOLDER_NUM_RATIO": None,
        "AVG_HOLD_NUM": None,
        "AVG_MARKET_CAP": None,
        "TOTAL_MARKET_CAP": None,
        "TOTAL_A_SHARES": None,
    }


def fixture_shareholder_pages(
    peer: dict[str, str], end: dt.date, scenario: str, peer_index: int
) -> Iterable[list[dict[str, Any]]]:
    if scenario == "malformed-response":
        _, data = validate_response({"success": True, "result": {"pages": 1, "data": None}})
        return [data]
    if scenario in {"all-failure", "shareholder-all-failure"} or (
        scenario == "partial-failure" and peer_index == 0
    ):
        raise RuntimeError("fixture shareholder count failure")
    if scenario == "no-data":
        return [[]]
    if scenario == "early-stop-before-failure":
        return page_then_failure(
            [fixture_shareholder_record(peer, end - dt.timedelta(days=30), end - dt.timedelta(days=20))],
            "fixture unexpected shareholder next-page request",
        )
    if scenario == "as-of-pagination":
        return [
            [fixture_shareholder_record(peer, end - dt.timedelta(days=30), end + dt.timedelta(days=1))],
            [fixture_shareholder_record(peer, end - dt.timedelta(days=60), end - dt.timedelta(days=1))],
        ]
    first = fixture_shareholder_record(peer, end - dt.timedelta(days=30), end - dt.timedelta(days=20))
    second = fixture_shareholder_record(
        peer, end - dt.timedelta(days=120), end - dt.timedelta(days=100), calculated=True
    )
    if scenario == "invalid-row":
        bad = dict(first)
        bad["HOLD_NOTICE_DATE"] = None
        return [[bad, second]]
    if scenario == "all-invalid-records":
        bad = dict(first)
        bad["HOLD_NOTICE_DATE"] = None
        return [[bad]]
    if scenario == "filtered-plus-invalid":
        bad = dict(first)
        bad["HOLD_NOTICE_DATE"] = None
        future = fixture_shareholder_record(
            peer,
            end - dt.timedelta(days=30),
            end + dt.timedelta(days=1),
        )
        return [[future, bad]]
    if scenario == "insufficient-derived":
        first["PRE_HOLDER_NUM"] = None
        first["HOLDER_NUM_CHANGE"] = None
        first["HOLDER_NUM_RATIO"] = None
        return [[first]]
    if scenario == "derived-conflict":
        first["HOLDER_NUM_CHANGE"] = 99
        second["HOLDER_NUM_RATIO"] = 99
        return [[first, second]]
    return [[first, second]]


def decimal_value(
    value: Any,
    field: str,
    *,
    required: bool = False,
    integer: bool = False,
    nonnegative: bool = True,
    positive: bool = False,
) -> Decimal | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(f"missing {field}")
        return None
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as exc:
        if required:
            raise ValueError(f"invalid {field}: {value!r}") from exc
        return None
    if (
        not parsed.is_finite()
        or (nonnegative and parsed < 0)
        or (positive and parsed <= 0)
        or (integer and parsed != parsed.to_integral_value())
    ):
        if required:
            raise ValueError(f"invalid {field}: {value!r}")
        return None
    return parsed


def decimal_text(value: Decimal | None, *, integer: bool = False) -> str:
    if value is None:
        return MISSING
    if integer:
        return str(int(value))
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


def rounded_text(value: Decimal | None, places: str) -> str:
    if value is None:
        return MISSING
    rounded = value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    return decimal_text(rounded, integer=places == "1")


def normalize_record(
    record: dict[str, Any],
    peer: dict[str, str],
    begin: dt.date,
    end: dt.date,
    basis: str,
) -> tuple[dict[str, str] | None, list[str]]:
    try:
        raw_code = str(record.get("SECURITY_CODE") or "").strip()
        if not raw_code:
            raise ValueError("missing SECURITY_CODE")
        code = normalize_a_share_code(raw_code)
        if code != peer["code"]:
            raise ValueError(f"unexpected SECURITY_CODE {raw_code!r} for {peer['code']}")
        trade_date = dt.date.fromisoformat(str(record.get("TRADE_DATE") or "")[:10])
        if trade_date < begin or trade_date > end:
            return None, []
        deal_price = decimal_value(
            record.get("DEAL_PRICE"), "DEAL_PRICE", required=True, positive=True
        )
        volume = decimal_value(
            record.get("DEAL_VOLUME"),
            "DEAL_VOLUME",
            required=True,
            integer=True,
            positive=True,
        )
        amount = decimal_value(
            record.get("DEAL_AMT"), "DEAL_AMT", required=True, positive=True
        )
        close = decimal_value(record.get("CLOSE_PRICE"), "CLOSE_PRICE")
        source_premium = decimal_value(
            record.get("PREMIUM_RATIO"),
            "PREMIUM_RATIO",
            nonnegative=False,
        )
        calculated = None
        if close is not None and close > 0 and deal_price is not None:
            calculated = (deal_price - close) / close * Decimal(100)
        conflict = None
        if source_premium is not None:
            if calculated is not None and abs(source_premium - calculated) > PERCENT_TOLERANCE:
                premium_text = MISSING
                premium_basis = MISSING
                conflict = (
                    f"PREMIUM_RATIO {decimal_text(source_premium)} conflicts with calculated "
                    f"{decimal_text(calculated)} beyond 0.02 percentage points"
                )
            else:
                premium_text = decimal_text(source_premium)
                premium_basis = "source"
        elif calculated is not None:
            premium_text = decimal_text(calculated)
            premium_basis = "calculated"
        else:
            premium_text = MISSING
            premium_basis = MISSING
        row = {
            "block_trade_id": "",
            "security_code": code,
            "security_name": str(record.get("SECURITY_NAME_ABBR") or peer.get("name") or MISSING).strip() or MISSING,
            "trade_date": trade_date.isoformat(),
            "close_price_cny": decimal_text(close),
            "deal_price_cny": decimal_text(deal_price),
            "deal_volume_shares": decimal_text(volume, integer=True),
            "deal_amount_cny": decimal_text(amount),
            "premium_discount_pct": premium_text,
            "premium_discount_pct_basis": premium_basis,
            "buyer_name": str(record.get("BUYER_NAME") or MISSING).strip() or MISSING,
            "seller_name": str(record.get("SELLER_NAME") or MISSING).strip() or MISSING,
            "source_type": "public_market_data",
            "source_name": BLOCK_SOURCE_NAME,
            "verification_status": "待验证",
            "basis": basis,
        }
        return row, [conflict] if conflict else []
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(str(exc)) from exc


def normalize_shareholder_record(
    record: dict[str, Any],
    peer: dict[str, str],
    begin: dt.date,
    end: dt.date,
    basis: str,
) -> tuple[dict[str, str] | None, list[str]]:
    """规范股东户数源记录，并逐字段隔离派生冲突。"""
    raw_code = str(record.get("SECURITY_CODE") or "").strip()
    if not raw_code:
        raise ValueError("missing SECURITY_CODE")
    code = normalize_a_share_code(raw_code)
    if code != peer["code"]:
        raise ValueError(f"unexpected SECURITY_CODE {raw_code!r} for {peer['code']}")
    try:
        statistical_end = dt.date.fromisoformat(str(record.get("END_DATE") or "")[:10])
    except ValueError as exc:
        raise ValueError("missing or invalid END_DATE") from exc
    try:
        announcement = dt.date.fromisoformat(str(record.get("HOLD_NOTICE_DATE") or "")[:10])
    except ValueError as exc:
        raise ValueError("missing or invalid HOLD_NOTICE_DATE") from exc
    if statistical_end < begin or statistical_end > end or announcement > end:
        return None, []

    current = decimal_value(record.get("HOLDER_NUM"), "HOLDER_NUM", required=True, integer=True, positive=True)
    previous = decimal_value(record.get("PRE_HOLDER_NUM"), "PRE_HOLDER_NUM", integer=True, positive=True)
    source_change = decimal_value(
        record.get("HOLDER_NUM_CHANGE"), "HOLDER_NUM_CHANGE", integer=True, nonnegative=False
    )
    source_pct = decimal_value(record.get("HOLDER_NUM_RATIO"), "HOLDER_NUM_RATIO", nonnegative=False)
    calculated_change = current - previous if current is not None and previous is not None else None
    calculated_pct = (
        calculated_change / previous * Decimal(100)
        if calculated_change is not None and previous is not None and previous != 0
        else None
    )
    conflicts: list[str] = []
    if source_change is not None:
        if calculated_change is not None and source_change != calculated_change:
            change_text = change_basis = MISSING
            conflicts.append(
                f"HOLDER_NUM_CHANGE {decimal_text(source_change, integer=True)} conflicts with calculated "
                f"{decimal_text(calculated_change, integer=True)}"
            )
        else:
            change_text = decimal_text(source_change, integer=True)
            change_basis = "source"
    elif calculated_change is not None:
        change_text = decimal_text(calculated_change, integer=True)
        change_basis = "calculated"
    else:
        change_text = change_basis = MISSING

    if source_pct is not None:
        if calculated_pct is not None and abs(source_pct - calculated_pct) > PERCENT_TOLERANCE:
            pct_text = pct_basis = MISSING
            conflicts.append(
                f"HOLDER_NUM_RATIO {decimal_text(source_pct)} conflicts with calculated "
                f"{decimal_text(calculated_pct)} beyond 0.02 percentage points"
            )
        else:
            pct_text = decimal_text(source_pct)
            pct_basis = "source"
    elif calculated_pct is not None:
        pct_text = decimal_text(calculated_pct)
        pct_basis = "calculated"
    else:
        pct_text = pct_basis = MISSING

    average_holding = decimal_value(record.get("AVG_HOLD_NUM"), "AVG_HOLD_NUM")
    average_value = decimal_value(record.get("AVG_MARKET_CAP"), "AVG_MARKET_CAP")
    total_market_cap = decimal_value(record.get("TOTAL_MARKET_CAP"), "TOTAL_MARKET_CAP")
    total_shares = decimal_value(record.get("TOTAL_A_SHARES"), "TOTAL_A_SHARES", integer=True)
    row = {
        "shareholder_snapshot_id": "",
        "security_code": code,
        "security_name": str(record.get("SECURITY_NAME_ABBR") or peer.get("name") or MISSING).strip() or MISSING,
        "statistical_end_date": statistical_end.isoformat(),
        "announcement_date": announcement.isoformat(),
        "holder_count": decimal_text(current, integer=True),
        "previous_holder_count": decimal_text(previous, integer=True),
        "holder_count_change": change_text,
        "holder_count_change_basis": change_basis,
        "holder_count_change_pct": pct_text,
        "holder_count_change_pct_basis": pct_basis,
        "average_holding_shares": rounded_text(average_holding, "1"),
        "average_holding_market_value_cny": rounded_text(average_value, "0.01"),
        "total_market_cap_cny": rounded_text(total_market_cap, "0.01"),
        "total_shares": decimal_text(total_shares, integer=True),
        "source_type": "public_market_data",
        "source_name": SHAREHOLDER_SOURCE_NAME,
        "verification_status": "待验证",
        "basis": basis,
    }
    return row, conflicts


def identity(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row["security_code"], row["trade_date"], row["deal_price_cny"],
        row["deal_volume_shares"], row["deal_amount_cny"], row["buyer_name"], row["seller_name"],
    )


def assign_stable_ids(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    ordered = sorted(rows, key=lambda row: (row["trade_date"], identity(row)), reverse=True)
    totals = Counter(identity(row) for row in ordered)
    occurrences: defaultdict[tuple[str, ...], int] = defaultdict(int)
    result: list[dict[str, str]] = []
    for row in ordered:
        key = identity(row)
        occurrences[key] += 1
        ordinal = occurrences[key] if totals[key] > 1 else 1
        material = json.dumps([*key, ordinal], ensure_ascii=False, separators=(",", ":"))
        item = dict(row)
        item["block_trade_id"] = "bt_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        result.append(item)
    return sorted(result, key=lambda row: (row["security_code"], row["block_trade_id"]))


def select_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    with_ids = assign_stable_ids(rows)
    selected: list[dict[str, str]] = []
    counts: defaultdict[str, int] = defaultdict(int)
    ordered = sorted(
        with_ids,
        key=lambda row: (
            -int(row["trade_date"].replace("-", "")),
            row["security_code"],
            row["block_trade_id"],
        ),
    )
    for row in ordered:
        if counts[row["security_code"]] < limit:
            selected.append(row)
            counts[row["security_code"]] += 1
    return selected


def assign_shareholder_ids(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["security_code"], row["statistical_end_date"], row["announcement_date"])
        unique.setdefault(key, row)
    result: list[dict[str, str]] = []
    for key, row in unique.items():
        material = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
        item = dict(row)
        item["shareholder_snapshot_id"] = "sh_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        result.append(item)
    return result


def select_shareholder_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    counts: defaultdict[str, int] = defaultdict(int)
    selected: list[dict[str, str]] = []
    ordered = sorted(
        assign_shareholder_ids(rows),
        key=lambda row: (
            -int(row["statistical_end_date"].replace("-", "")),
            -int(row["announcement_date"].replace("-", "")),
            row["security_code"],
            row["shareholder_snapshot_id"],
        ),
    )
    for row in ordered:
        if counts[row["security_code"]] < limit:
            selected.append(row)
            counts[row["security_code"]] += 1
    return selected


def write_source_manifest(
    output_dir: Path,
    as_of: str,
    block_lookback_days: int,
    block_limit: int,
    shareholder_lookback_days: int,
    shareholder_limit: int,
) -> None:
    path = output_dir / "source_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"files": []}
    files = data.setdefault("files", [])
    files[:] = [
        item for item in files
        if item.get("file") not in {"block_trades.csv", "shareholder_counts.csv"}
    ]
    files.append(
        {
            "file": "block_trades.csv",
            "source_type": "public_market_data",
            "source_name": BLOCK_SOURCE_NAME,
            "data_time": as_of[:10],
            "period_or_basis": (
                f"RPT_DATA_BLOCKTRADE；截至 {as_of[:10]} 回溯 {block_lookback_days} 天；"
                f"每证券最多 {block_limit} 笔；先按 as-of、窗口和核心字段过滤，再按交易日降序、"
                "证券代码及稳定标识升序截断；API 的价格/成交额为人民币元、成交量为股，"
                "均为基础单位，网页可能另以万元或万股展示，不重复缩放"
            ),
            "verification_status": "待验证",
            "missing_behavior": (
                "无数据写 block_trade_no_data；请求、结构或解析失败写 block_trade；"
                "当前查询可能受来源后续修订影响；大宗交易事实不得推断机构吸筹、主力买卖、"
                "利益输送、资金意图或后续价格方向"
            ),
        }
    )
    files.append(
        {
            "file": "shareholder_counts.csv",
            "source_type": "public_market_data",
            "source_name": SHAREHOLDER_SOURCE_NAME,
            "data_time": as_of[:10],
            "period_or_basis": (
                f"RPT_HOLDERNUM_DET 个股历史详情；统计截止日截至 {as_of[:10]} 回溯 "
                f"{shareholder_lookback_days} 天，且公告日存在并不晚于研究截止日；每证券最多 "
                f"{shareholder_limit} 个可见快照；完整分页后先过滤再按统计截止日、公告日降序、"
                "证券代码及稳定标识升序截断；户数、股数和人民币元均采用 API 基础单位，"
                "网页可能以万或亿展示，不重复换算"
            ),
            "verification_status": "待验证",
            "missing_behavior": (
                "无数据写 shareholder_count_no_data；请求、结构或解析失败写 shareholder_count；"
                "来源可能后续修订；股东户数事实不得推断筹码集中、主力吸筹、买卖方向、"
                "股东结构评分或价格因果"
            ),
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_fetch_errors(output_dir: Path, errors: list[dict[str, str]]) -> None:
    path = output_dir / "fetch_errors.csv"
    existing: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = [
                row for row in csv.DictReader(handle)
                if row.get("stage") != "market_activity_input"
                and not row.get("stage", "").startswith("block_trade")
                and not row.get("stage", "").startswith("shareholder_count")
            ]
    write_csv(path, existing + errors, ERROR_COLUMNS)


def write_outputs(
    output_dir: Path,
    block_rows: list[dict[str, str]],
    shareholder_rows: list[dict[str, str]],
    errors: list[dict[str, str]],
    as_of: str,
    block_lookback_days: int,
    block_limit: int,
    shareholder_lookback_days: int,
    shareholder_limit: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "block_trades.csv", block_rows, BLOCK_COLUMNS)
    write_csv(output_dir / "shareholder_counts.csv", shareholder_rows, SHAREHOLDER_COLUMNS)
    write_source_manifest(
        output_dir,
        as_of,
        block_lookback_days,
        block_limit,
        shareholder_lookback_days,
        shareholder_limit,
    )
    write_fetch_errors(output_dir, errors)


PageLoader = Callable[[], Iterable[list[dict[str, Any]]]]
RecordNormalizer = Callable[[dict[str, Any]], tuple[dict[str, str] | None, list[str]]]


def collect_peer_dataset(
    peer: dict[str, str],
    load_pages: PageLoader,
    normalize: RecordNormalizer,
    source_key: str,
    failure_stage: str,
    no_data_stage: str,
    no_data_message: str,
    limit: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    raw_count = 0
    rejected_count = 0
    try:
        for page in load_pages():
            raw_count += len(page)
            for raw in page:
                try:
                    row, conflicts = normalize(raw)
                    if row is not None:
                        rows.append(row)
                    for conflict in conflicts:
                        errors.append(error_row(peer["code"], source_key, failure_stage, conflict))
                except ValueError as exc:
                    rejected_count += 1
                    errors.append(error_row(peer["code"], source_key, failure_stage, str(exc)))
            if len(rows) >= limit:
                break
    except Exception as exc:
        errors.append(error_row(peer["code"], source_key, failure_stage, str(exc)))
        return [], errors, True

    all_records_rejected = raw_count > 0 and rejected_count == raw_count
    if not rows and not all_records_rejected:
        errors.append(error_row(peer["code"], source_key, no_data_stage, no_data_message))
    return rows, errors, all_records_rejected


def run_pipeline(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    errors: list[dict[str, str]] = []
    block_rows: list[dict[str, str]] = []
    shareholder_rows: list[dict[str, str]] = []
    block_failures = 0
    shareholder_failures = 0
    valid_peer_count = 0
    try:
        if args.block_trade_lookback_days < 1:
            raise ValueError("--block-trade-lookback-days must be positive")
        if args.block_trade_limit_per_security < 1:
            raise ValueError("--block-trade-limit-per-security must be positive")
        if args.shareholder_lookback_days < 1:
            raise ValueError("--shareholder-lookback-days must be positive")
        if args.shareholder_limit_per_security < 1:
            raise ValueError("--shareholder-limit-per-security must be positive")
        end = parse_as_of(args.as_of)
        block_begin = end - dt.timedelta(days=args.block_trade_lookback_days)
        shareholder_begin = end - dt.timedelta(days=args.shareholder_lookback_days)
        peers, input_errors = read_peer_universe(Path(args.peer_universe))
        errors.extend(input_errors)
        valid_peer_count = len(peers)
        block_basis = (
            f"截至 {end.isoformat()} 回溯 {args.block_trade_lookback_days} 天；"
            f"每证券最多 {args.block_trade_limit_per_security} 笔；市场行为事实仅作后续核查线索"
        )
        shareholder_basis = (
            f"统计截止日截至 {end.isoformat()} 回溯 {args.shareholder_lookback_days} 天，"
            f"公告日不晚于研究截止日；每证券最多 {args.shareholder_limit_per_security} 个；"
            "市场行为事实仅作后续核查线索"
        )
        for peer_index, peer in enumerate(peers):
            peer_block_rows, peer_block_errors, block_failed = collect_peer_dataset(
                peer,
                lambda: (
                    fixture_pages(peer, end, args.fixture_scenario, peer_index)
                    if args.source == "fixture"
                    else fetch_eastmoney_pages(peer, block_begin, end)
                ),
                lambda raw: normalize_record(raw, peer, block_begin, end, block_basis),
                BLOCK_SOURCE_KEY,
                "block_trade",
                "block_trade_no_data",
                f"截至 {end.isoformat()} 回溯 {args.block_trade_lookback_days} 天未返回可用大宗交易",
                args.block_trade_limit_per_security,
            )
            block_rows.extend(peer_block_rows)
            errors.extend(peer_block_errors)
            if block_failed:
                block_failures += 1

            peer_shareholder_rows, peer_shareholder_errors, shareholder_failed = collect_peer_dataset(
                peer,
                lambda: (
                    fixture_shareholder_pages(peer, end, args.fixture_scenario, peer_index)
                    if args.source == "fixture"
                    else fetch_shareholder_eastmoney_pages(peer)
                ),
                lambda raw: normalize_shareholder_record(
                    raw, peer, shareholder_begin, end, shareholder_basis
                ),
                SHAREHOLDER_SOURCE_KEY,
                "shareholder_count",
                "shareholder_count_no_data",
                f"截至 {end.isoformat()} 回溯 {args.shareholder_lookback_days} 天未返回可见股东户数快照",
                args.shareholder_limit_per_security,
            )
            shareholder_rows.extend(peer_shareholder_rows)
            errors.extend(peer_shareholder_errors)
            if shareholder_failed:
                shareholder_failures += 1
        block_rows = select_rows(block_rows, args.block_trade_limit_per_security)
        shareholder_rows = select_shareholder_rows(
            shareholder_rows, args.shareholder_limit_per_security
        )
    except Exception as exc:
        errors.append(error_row(MISSING, BLOCK_SOURCE_KEY, "market_activity_input", str(exc)))
        write_outputs(
            output_dir,
            [],
            [],
            errors,
            args.as_of,
            args.block_trade_lookback_days,
            args.block_trade_limit_per_security,
            args.shareholder_lookback_days,
            args.shareholder_limit_per_security,
        )
        print(f"market activity input failed: {exc}", file=sys.stderr)
        return 1

    write_outputs(
        output_dir,
        block_rows,
        shareholder_rows,
        errors,
        args.as_of,
        args.block_trade_lookback_days,
        args.block_trade_limit_per_security,
        args.shareholder_lookback_days,
        args.shareholder_limit_per_security,
    )
    print(f"wrote block trade and shareholder market activity: {output_dir}")
    if errors:
        print(f"completed with {len(errors)} market activity notice(s)", file=sys.stderr)
    both_failed = (
        valid_peer_count > 0
        and block_failures == valid_peer_count
        and shareholder_failures == valid_peer_count
    )
    return 1 if both_failed else 0


def main() -> int:
    return run_pipeline(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
