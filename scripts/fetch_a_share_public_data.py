#!/usr/bin/env python3
"""Fetch public A-share market snapshot and financial summary data."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import http.client
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, TypeVar

MISSING = "来源缺失"
USER_AGENT = "Mozilla/5.0 a-share-market-researcher/0.1"
AKSHARE_RETRY_ATTEMPTS = 3
AKSHARE_RETRY_DELAY_SECONDS = 0.5
AKSHARE_RETRY_MAX_DELAY_SECONDS = 4.0
T = TypeVar("T")

MARKET_COLUMNS = [
    "code",
    "price",
    "pct_change",
    "amount",
    "turnover_rate",
    "volume_ratio",
    "amplitude",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "return_5d",
    "return_20d",
    "return_60d",
    "return_120d",
    "return_basis",
    "snapshot_time",
    "basis",
]

FINANCIAL_COLUMNS = [
    "code",
    "period",
    "revenue",
    "revenue_growth",
    "net_profit",
    "deducted_net_profit",
    "gross_margin",
    "net_margin",
    "roe",
    "asset_liability_ratio",
    "operating_cash_flow",
    "basis",
]

ERROR_COLUMNS = ["code", "source", "stage", "error"]


class FinancialSourceError(RuntimeError):
    def __init__(self, errors: list[dict[str, str]], rows: list[dict[str, str]]) -> None:
        super().__init__("explicit financial source failed")
        self.errors = errors
        self.rows = rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="CSV with A-share peers.")
    parser.add_argument("--output-dir", required=True, help="Directory for fetched files.")
    parser.add_argument("--as-of", required=True, help="Access time or snapshot timestamp.")
    parser.add_argument(
        "--market-source",
        choices=["tencent", "eastmoney", "fixture"],
        default="tencent",
        help="Market data source.",
    )
    parser.add_argument(
        "--financial-source",
        choices=["eastmoney", "akshare", "fixture"],
        default="eastmoney",
        help="Financial summary data source.",
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
    if symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{symbol}.SZ"
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


def eastmoney_secid(code: str) -> str:
    normalized = normalize_a_share_code(code)
    symbol, exchange = normalized.split(".", 1)
    if exchange == "SH":
        return f"1.{symbol}"
    return f"0.{symbol}"


def tencent_symbol(code: str) -> str:
    normalized = normalize_a_share_code(code)
    symbol, exchange = normalized.split(".", 1)
    prefix = "sh" if exchange == "SH" else "sz"
    return f"{prefix}{symbol}"


def read_peer_universe(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty peer universe: {path}")
    if any("code" not in row or not row["code"].strip() for row in rows):
        raise ValueError(f"peer universe requires non-empty code column: {path}")
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def log_step(message: str) -> None:
    print(f"[a-share-public-data] {message}", file=sys.stderr)


def record_fetch_error(
    errors: list[dict[str, str]],
    code: str,
    source: str,
    stage: str,
    exc: Exception | str,
) -> None:
    error = {"code": code, "source": source, "stage": stage, "error": str(exc)}
    errors.append(error)
    log_step(f"{stage} failed: code={code} source={source} error={exc}")


def fetch_text(url: str, params: dict[str, str], encoding: str = "utf-8") -> str:
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    request = urllib.request.Request(
        full_url,
        headers={"User-Agent": USER_AGENT},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=15) as response:
            return response.read().decode(encoding, errors="replace")
    except Exception:
        if not shutil.which("curl"):
            raise
        payload_bytes = subprocess.check_output(
            ["curl", "--noproxy", "*", "-L", "-sS", "--max-time", "15", full_url],
        )
        return payload_bytes.decode(encoding, errors="replace")


def fetch_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    payload = fetch_text(url, params)
    return json.loads(payload)


def clean_value(value: Any) -> str:
    if value in (None, "", "-", "--"):
        return MISSING
    return str(value)


def is_transient_akshare_error(exc: Exception) -> bool:
    if isinstance(exc, (http.client.RemoteDisconnected, ConnectionError, TimeoutError)):
        return True
    message = str(exc)
    transient_markers = [
        "Connection aborted",
        "Connection reset",
        "RemoteDisconnected",
        "Read timed out",
        "Max retries exceeded",
        "Temporary failure",
        "timed out",
    ]
    return any(marker in message for marker in transient_markers)


def akshare_retry_delay(attempt: int) -> float:
    return min(AKSHARE_RETRY_MAX_DELAY_SECONDS, AKSHARE_RETRY_DELAY_SECONDS * (2**attempt))


def fetch_akshare_with_retries(operation: Callable[[], T], label: str = "AkShare operation") -> T:
    last_exc: Exception | None = None
    for attempt in range(AKSHARE_RETRY_ATTEMPTS):
        try:
            return operation()
        except Exception as exc:
            if not is_transient_akshare_error(exc):
                raise
            last_exc = exc
            attempt_no = attempt + 1
            if attempt == AKSHARE_RETRY_ATTEMPTS - 1:
                log_step(f"{label} failed after {attempt_no}/{AKSHARE_RETRY_ATTEMPTS}: {exc}")
                break
            if AKSHARE_RETRY_DELAY_SECONDS > 0:
                delay = akshare_retry_delay(attempt)
                log_step(
                    f"{label} transient failure {attempt_no}/{AKSHARE_RETRY_ATTEMPTS}; "
                    f"retrying in {delay}s: {exc}"
                )
                time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("AkShare retry operation did not run")


def format_tencent_time(value: str) -> str:
    if len(value) != 14 or not value.isdigit():
        return clean_value(value)
    return (
        f"{value[0:4]}-{value[4:6]}-{value[6:8]} "
        f"{value[8:10]}:{value[10:12]}:{value[12:14]}"
    )


def yuan_from_yi(value: str) -> str:
    if value in ("", MISSING):
        return MISSING
    return str(round(float(value) * 100000000, 2))


def format_percent(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def calculate_price_performance(price_rows: list[dict[str, Any]]) -> dict[str, str]:
    closes: list[tuple[str, float]] = []
    for row in price_rows:
        close = row.get("收盘", row.get("close"))
        trade_date = str(row.get("日期", row.get("date", "")))
        try:
            closes.append((trade_date, float(close)))
        except (TypeError, ValueError):
            continue

    if not closes:
        return {
            "return_5d": MISSING,
            "return_20d": MISSING,
            "return_60d": MISSING,
            "return_120d": MISSING,
            "return_basis": MISSING,
        }

    latest_date, latest_close = closes[-1]
    result: dict[str, str] = {
        "return_5d": MISSING,
        "return_20d": MISSING,
        "return_60d": MISSING,
        "return_120d": MISSING,
        "return_basis": MISSING,
    }
    for label, offset in [("return_5d", 6), ("return_20d", 21), ("return_60d", 61), ("return_120d", 121)]:
        if len(closes) >= offset and closes[-offset][1] != 0:
            result[label] = format_percent((latest_close / closes[-offset][1] - 1) * 100)
    if any(result[k] != MISSING for k in ("return_5d", "return_20d", "return_60d", "return_120d")):
        result["return_basis"] = f"AkShare 前复权收盘价，截至 {latest_date}"
    return result


def akshare_date_window(as_of: str) -> tuple[str, str]:
    try:
        end_date = dt.date.fromisoformat(as_of[:10])
    except ValueError:
        end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=200)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def fetch_akshare_price_performance(code: str, as_of: str) -> dict[str, str]:
    import akshare as ak  # type: ignore[import-not-found]

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    start_date, end_date = akshare_date_window(as_of)
    frame = fetch_akshare_with_retries(
        lambda: ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        ),
        label=f"stock_zh_a_hist {symbol}",
    )
    return calculate_price_performance(frame.to_dict("records"))


def fetch_tencent_price_performance(code: str) -> dict[str, str]:
    symbol = tencent_symbol(code)
    data = fetch_json(
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
        {"param": f"{symbol},day,,,130,qfq"},
    )
    payload = data.get("data", {}).get(symbol, {})
    kline_rows = payload.get("qfqday") or payload.get("day") or []
    price_rows = [
        {"date": row[0], "close": row[2]}
        for row in kline_rows
        if isinstance(row, list) and len(row) >= 3
    ]
    result = calculate_price_performance(price_rows)
    if result["return_basis"] != MISSING:
        latest_date = price_rows[-1]["date"]
        result["return_basis"] = f"腾讯前复权日 K 线，截至 {latest_date}"
    return result


_AKSHARE_SPOT_CACHE: dict[str, dict[str, str]] | None = None


def _load_akshare_spot_cache() -> dict[str, dict[str, str]]:
    global _AKSHARE_SPOT_CACHE
    if _AKSHARE_SPOT_CACHE is not None:
        return _AKSHARE_SPOT_CACHE
    import akshare as ak  # type: ignore[import-not-found]

    frame = fetch_akshare_with_retries(
        lambda: ak.stock_zh_a_spot_em(),
        label="stock_zh_a_spot_em",
    )
    cache: dict[str, dict[str, str]] = {}
    for _, row in frame.iterrows():
        code_raw = str(row.get("代码", ""))
        if not code_raw:
            continue
        normalized = normalize_a_share_code(code_raw)
        cache[normalized] = {
            "volume_ratio": clean_value(row.get("量比")),
            "amplitude": clean_value(row.get("振幅")),
        }
    _AKSHARE_SPOT_CACHE = cache
    return cache


def fetch_akshare_spot_fields(code: str) -> dict[str, str]:
    cache = _load_akshare_spot_cache()
    normalized = normalize_a_share_code(code)
    entry = cache.get(normalized, {})
    return {
        "volume_ratio": entry.get("volume_ratio", MISSING),
        "amplitude": entry.get("amplitude", MISSING),
    }


def fetch_akshare_ps_ttm(code: str) -> dict[str, str]:
    import akshare as ak  # type: ignore[import-not-found]

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    frame = fetch_akshare_with_retries(
        lambda: ak.stock_value_em(symbol=symbol),
        label=f"stock_value_em {symbol}",
    )
    records = frame.to_dict("records")
    if not records:
        return {"ps_ttm": MISSING}
    latest = records[-1]
    return {"ps_ttm": clean_value(latest.get("市销率", latest.get("PS_TTM")))}


def fetch_eastmoney_market_row(code: str, as_of: str) -> dict[str, str]:
    data = fetch_json(
        "https://push2.eastmoney.com/api/qt/stock/get",
        {
            "secid": eastmoney_secid(code),
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fields": "f43,f48,f57,f58,f116,f117,f162,f167,f168,f170",
            "invt": "2",
            "fltt": "2",
        },
    )
    payload = data.get("data") or {}
    return {
        "code": normalize_a_share_code(code),
        "price": clean_value(payload.get("f43")),
        "pct_change": clean_value(payload.get("f170")),
        "amount": clean_value(payload.get("f48")),
        "turnover_rate": clean_value(payload.get("f168")),
        "volume_ratio": MISSING,
        "amplitude": MISSING,
        "market_cap": clean_value(payload.get("f116")),
        "float_market_cap": clean_value(payload.get("f117")),
        "pe_ttm": clean_value(payload.get("f162") or payload.get("f167")),
        "pb": MISSING,
        "ps_ttm": MISSING,
        "return_5d": MISSING,
        "return_20d": MISSING,
        "return_60d": MISSING,
        "return_120d": MISSING,
        "return_basis": MISSING,
        "snapshot_time": as_of,
        "basis": "东方财富行情快照",
    }


def fetch_tencent_market_row(code: str, as_of: str) -> dict[str, str]:
    normalized = normalize_a_share_code(code)
    data = fetch_text(
        "https://qt.gtimg.cn/q",
        {"q": tencent_symbol(normalized)},
        encoding="gbk",
    )
    quote = data.split('"', 2)[1] if '"' in data else ""
    fields = quote.split("~")
    if len(fields) < 58:
        raise ValueError(f"unexpected Tencent quote shape for {normalized}")

    amount = MISSING
    trade_triplet = fields[35].split("/")
    if len(trade_triplet) >= 3:
        amount = clean_value(trade_triplet[2])

    return {
        "code": normalized,
        "price": clean_value(fields[3]),
        "pct_change": clean_value(fields[32]),
        "amount": amount,
        "turnover_rate": clean_value(fields[38]),
        "volume_ratio": clean_value(fields[49]),
        "amplitude": clean_value(fields[43]),
        "market_cap": yuan_from_yi(fields[45]),
        "float_market_cap": yuan_from_yi(fields[44]),
        "pe_ttm": clean_value(fields[52]),
        "pb": clean_value(fields[46]),
        "ps_ttm": MISSING,
        "return_5d": MISSING,
        "return_20d": MISSING,
        "return_60d": MISSING,
        "return_120d": MISSING,
        "return_basis": MISSING,
        "snapshot_time": format_tencent_time(fields[30]) if fields[30] else as_of,
        "basis": "腾讯行情 API 快照",
    }


def fixture_market_row(code: str, as_of: str) -> dict[str, str]:
    normalized = normalize_a_share_code(code)
    numeric_tail = int(normalized[:6][-2:])
    return {
        "code": normalized,
        "price": f"{20 + numeric_tail / 10:.2f}",
        "pct_change": f"{numeric_tail / 100:.2f}",
        "amount": str(100000000 + numeric_tail * 10000),
        "turnover_rate": f"{1 + numeric_tail / 100:.2f}",
        "volume_ratio": f"{1 + numeric_tail / 100:.2f}",
        "amplitude": f"{numeric_tail / 10:.2f}",
        "market_cap": str(10000000000 + numeric_tail * 1000000),
        "float_market_cap": str(8000000000 + numeric_tail * 1000000),
        "pe_ttm": f"{20 + numeric_tail / 10:.2f}",
        "pb": f"{2 + numeric_tail / 100:.2f}",
        "ps_ttm": f"{4 + numeric_tail / 100:.2f}",
        "return_5d": format_percent(numeric_tail / 10),
        "return_20d": format_percent(numeric_tail / 4),
        "return_60d": format_percent(numeric_tail / 2),
        "return_120d": format_percent(numeric_tail),
        "return_basis": "fixture AkShare 前复权收盘价短期收益率",
        "snapshot_time": as_of,
        "basis": "fixture public market snapshot",
    }


def fetch_market_snapshot(
    peers: list[dict[str, str]],
    source: str,
    as_of: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    log_step(f"market_snapshot start: source={source} peers={len(peers)}")
    # Eastmoney does not expose all spot indicators used by downstream comps.
    spot_cache_loaded = False
    if source == "eastmoney":
        try:
            log_step("loading AkShare spot cache for volume_ratio and amplitude")
            _load_akshare_spot_cache()
            spot_cache_loaded = True
        except Exception as exc:
            record_fetch_error(errors, "*", "akshare", "spot_cache", exc)

    for index, peer in enumerate(peers, start=1):
        code = normalize_a_share_code(peer["code"])
        log_step(f"market_snapshot {index}/{len(peers)}: code={code} source={source}")
        try:
            if source == "fixture":
                rows.append(fixture_market_row(code, as_of))
            elif source == "tencent":
                row = fetch_tencent_market_row(code, as_of)
                try:
                    row.update(fetch_akshare_price_performance(code, as_of))
                except Exception as exc:
                    try:
                        row.update(fetch_tencent_price_performance(code))
                        log_step(f"price_performance fallback used: code={code} source=tencent")
                    except Exception as fallback_exc:
                        record_fetch_error(
                            errors,
                            code,
                            "akshare",
                            "price_performance",
                            f"{exc}; tencent fallback failed: {fallback_exc}",
                        )
                if spot_cache_loaded:
                    row.update(fetch_akshare_spot_fields(code))
                try:
                    row.update(fetch_akshare_ps_ttm(code))
                except Exception as exc:
                    record_fetch_error(errors, code, "akshare", "ps_ttm", exc)
                rows.append(row)
            else:
                row = fetch_eastmoney_market_row(code, as_of)
                try:
                    row.update(fetch_akshare_price_performance(code, as_of))
                except Exception as exc:
                    record_fetch_error(errors, code, "akshare", "price_performance", exc)
                if spot_cache_loaded:
                    row.update(fetch_akshare_spot_fields(code))
                try:
                    row.update(fetch_akshare_ps_ttm(code))
                except Exception as exc:
                    record_fetch_error(errors, code, "akshare", "ps_ttm", exc)
                rows.append(row)
        except Exception as exc:
            record_fetch_error(errors, code, source, "market_snapshot", exc)
            rows.append(
                {
                    "code": code,
                    "price": MISSING,
                    "pct_change": MISSING,
                    "amount": MISSING,
                    "turnover_rate": MISSING,
                    "volume_ratio": MISSING,
                    "amplitude": MISSING,
                    "market_cap": MISSING,
                    "float_market_cap": MISSING,
                    "pe_ttm": MISSING,
                    "pb": MISSING,
                    "ps_ttm": MISSING,
                    "return_5d": MISSING,
                    "return_20d": MISSING,
                    "return_60d": MISSING,
                    "return_120d": MISSING,
                    "return_basis": MISSING,
                    "snapshot_time": as_of,
                    "basis": "抓取失败，字段降级为来源缺失",
                }
            )
    log_step(f"market_snapshot complete: rows={len(rows)} errors={len(errors)}")
    return rows, errors


def fixture_financial_row(code: str) -> dict[str, str]:
    normalized = normalize_a_share_code(code)
    numeric_tail = int(normalized[:6][-2:])
    return {
        "code": normalized,
        "period": "2025A",
        "revenue": str(1000000000 + numeric_tail * 1000000),
        "revenue_growth": f"{5 + numeric_tail / 10:.2f}",
        "net_profit": str(100000000 + numeric_tail * 100000),
        "deducted_net_profit": str(90000000 + numeric_tail * 100000),
        "gross_margin": f"{20 + numeric_tail / 10:.2f}",
        "net_margin": f"{8 + numeric_tail / 100:.2f}",
        "roe": f"{10 + numeric_tail / 100:.2f}",
        "asset_liability_ratio": f"{40 + numeric_tail / 100:.2f}",
        "operating_cash_flow": str(80000000 + numeric_tail * 100000),
        "basis": "fixture financial summary",
    }


def fetch_eastmoney_financial_row(code: str) -> dict[str, str]:
    data = fetch_json(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        {
            "reportName": "RPT_F10_FINANCE_MAINFINADATA",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{normalize_a_share_code(code)[:6]}")',
            "pageNumber": "1",
            "pageSize": "1",
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
        },
    )
    records = data.get("result", {}).get("data") or []
    record = records[0] if records else {}
    period = clean_value(record.get("REPORT_DATE") or record.get("REPORT_NAME"))
    return {
        "code": normalize_a_share_code(code),
        "period": period,
        "revenue": clean_value(record.get("TOTALOPERATEREVE") or record.get("OPERATE_INCOME_PK")),
        "revenue_growth": clean_value(record.get("TOTALOPERATEREVETZ") or record.get("DJD_TOI_YOY")),
        "net_profit": clean_value(record.get("PARENTNETPROFIT")),
        "deducted_net_profit": clean_value(record.get("KCFJCXSYJLR")),
        "gross_margin": clean_value(record.get("XSMLL")),
        "net_margin": clean_value(record.get("XSJLL")),
        "roe": clean_value(record.get("ROEJQ")),
        "asset_liability_ratio": clean_value(record.get("ZCFZL")),
        "operating_cash_flow": clean_value(record.get("NETCASH_OPERATE_PK")),
        "basis": "东方财富公开财务摘要",
    }


def first_present(record: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, "", "-", "--"):
            return value
    return None


def report_period(record: dict[str, Any]) -> str:
    return clean_value(
        first_present(record, ["报告期", "截止日期", "报表日期", "日期", "REPORT_DATE"])
    )


def is_akshare_wide_financial_table(records: list[dict[str, Any]]) -> bool:
    return any(
        first_present(record, ["指标", "项目", "关键指标", "index"]) is not None
        for record in records
    )


def period_keys_from_wide_table(records: list[dict[str, Any]]) -> list[str]:
    ignored = {"指标", "项目", "关键指标", "index"}
    keys: set[str] = set()
    for record in records:
        for key in record:
            if key not in ignored:
                keys.add(str(key))
    return sorted(keys)


def wide_metric_value(records: list[dict[str, Any]], metric_names: list[str], period: str) -> Any:
    for record in records:
        metric = clean_value(str(first_present(record, ["指标", "项目", "关键指标", "index"])))
        if metric in metric_names:
            return record.get(period)
    return None


def map_akshare_wide_financial_summary(code: str, records: list[dict[str, Any]]) -> dict[str, str]:
    periods = period_keys_from_wide_table(records)
    if not periods:
        return {column: MISSING for column in FINANCIAL_COLUMNS} | {"code": normalize_a_share_code(code)}

    latest_period = periods[-1]
    return {
        "code": normalize_a_share_code(code),
        "period": latest_period,
        "revenue": clean_value(wide_metric_value(records, ["营业总收入", "主营业务收入", "营业收入"], latest_period)),
        "revenue_growth": clean_value(
            wide_metric_value(records, ["营业总收入同比增长率", "主营业务收入增长率", "营业收入同比增长率"], latest_period)
        ),
        "net_profit": clean_value(wide_metric_value(records, ["归母净利润", "净利润", "母公司股东的净利润"], latest_period)),
        "deducted_net_profit": clean_value(wide_metric_value(records, ["扣非净利润", "扣除非经常性损益后的净利润"], latest_period)),
        "gross_margin": clean_value(wide_metric_value(records, ["销售毛利率", "毛利率"], latest_period)),
        "net_margin": clean_value(wide_metric_value(records, ["销售净利率", "净利率"], latest_period)),
        "roe": clean_value(wide_metric_value(records, ["净资产收益率", "净资产收益率-摊薄"], latest_period)),
        "asset_liability_ratio": clean_value(wide_metric_value(records, ["资产负债率"], latest_period)),
        "operating_cash_flow": clean_value(
            wide_metric_value(records, ["经营现金流量净额", "经营活动产生的现金流量净额", "经营活动现金流量净额"], latest_period)
        ),
        "basis": "AkShare stock_financial_abstract 最新一期财务摘要",
    }


def map_akshare_financial_summary(code: str, records: list[dict[str, Any]]) -> dict[str, str]:
    if not records:
        return {column: MISSING for column in FINANCIAL_COLUMNS} | {"code": normalize_a_share_code(code)}

    if is_akshare_wide_financial_table(records):
        return map_akshare_wide_financial_summary(code, records)

    latest = sorted(records, key=report_period)[-1]
    return {
        "code": normalize_a_share_code(code),
        "period": report_period(latest),
        "revenue": clean_value(first_present(latest, ["营业总收入", "主营业务收入", "营业收入"])),
        "revenue_growth": clean_value(
            first_present(latest, ["营业总收入同比增长率", "主营业务收入增长率", "营业收入同比增长率"])
        ),
        "net_profit": clean_value(first_present(latest, ["归母净利润", "净利润", "母公司股东的净利润"])),
        "deducted_net_profit": clean_value(first_present(latest, ["扣非净利润", "扣除非经常性损益后的净利润"])),
        "gross_margin": clean_value(first_present(latest, ["销售毛利率", "毛利率"])),
        "net_margin": clean_value(first_present(latest, ["销售净利率", "净利率"])),
        "roe": clean_value(first_present(latest, ["净资产收益率", "净资产收益率-摊薄"])),
        "asset_liability_ratio": clean_value(first_present(latest, ["资产负债率"])),
        "operating_cash_flow": clean_value(
            first_present(latest, ["经营现金流量净额", "经营活动产生的现金流量净额", "经营活动现金流量净额"])
        ),
        "basis": "AkShare stock_financial_abstract 最新一期财务摘要",
    }


def fetch_akshare_financial_row(code: str) -> dict[str, str]:
    import akshare as ak  # type: ignore[import-not-found]

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    try:
        frame = fetch_akshare_with_retries(
            lambda: ak.stock_financial_abstract(stock=symbol),
            label=f"stock_financial_abstract {symbol}",
        )
    except TypeError:
        frame = fetch_akshare_with_retries(
            lambda: ak.stock_financial_abstract(symbol=symbol),
            label=f"stock_financial_abstract {symbol}",
        )
    return map_akshare_financial_summary(code, frame.to_dict("records"))


def fetch_financial_summary(
    peers: list[dict[str, str]],
    source: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    log_step(f"financial_summary start: source={source} peers={len(peers)}")
    for index, peer in enumerate(peers, start=1):
        code = normalize_a_share_code(peer["code"])
        log_step(f"financial_summary {index}/{len(peers)}: code={code} source={source}")
        try:
            if source == "fixture":
                rows.append(fixture_financial_row(code))
            elif source == "eastmoney":
                rows.append(fetch_eastmoney_financial_row(code))
            else:
                rows.append(fetch_akshare_financial_row(code))
        except Exception as exc:
            record_fetch_error(errors, code, source, "financial_summary", exc)
            if source == "akshare":
                rows.append({column: MISSING for column in FINANCIAL_COLUMNS} | {"code": code})
                continue
            rows.append({column: MISSING for column in FINANCIAL_COLUMNS} | {"code": code})
    log_step(f"financial_summary complete: rows={len(rows)} errors={len(errors)}")
    if source == "akshare" and errors:
        raise FinancialSourceError(errors, rows)
    return rows, errors


def source_name(source: str, family: str) -> str:
    if source == "fixture":
        return f"fixture {family}"
    if source == "tencent":
        return "腾讯行情 API"
    if family == "market_snapshot":
        return "东方财富行情 API"
    if source == "akshare":
        return "AkShare stock_financial_abstract"
    return "东方财富公开财务摘要"


def verification_status(source: str) -> str:
    if source == "fixture":
        return "user_provided"
    return "verified"


def price_performance_source_name(market_source: str) -> str:
    if market_source == "fixture":
        return "fixture price_performance"
    if market_source == "tencent":
        return "AkShare stock_zh_a_hist; fallback 腾讯前复权日 K 线"
    return "AkShare stock_zh_a_hist"


def spot_indicators_source_name(market_source: str) -> str:
    if market_source == "fixture":
        return "fixture spot indicators"
    if market_source == "tencent":
        return "腾讯行情 API fields 43/49"
    return "AkShare stock_zh_a_spot_em"


def write_source_manifest(
    output_dir: Path,
    as_of: str,
    market_source: str,
    financial_source: str,
) -> None:
    payload = {
        "files": [
            {
                "file": "peer_universe.csv",
                "source_type": "user_provided",
                "source_name": "本地股票池",
                "data_time": as_of,
                "period_or_basis": "用户提供",
                "verification_status": "user_provided",
                "missing_behavior": "缺少股票池时停止 comps 和 idea shortlist",
            },
            {
                "file": "market_snapshot.csv",
                "source_type": "public_market_data",
                "source_name": source_name(market_source, "market_snapshot"),
                "data_time": as_of,
                "period_or_basis": "行情快照",
                "verification_status": verification_status(market_source),
                "missing_behavior": "缺失时行情、估值和流动性字段写来源缺失，不得用于排序",
            },
            {
                "file": "market_snapshot.csv",
                "field_group": "price_performance",
                "source_type": "public_market_data",
                "source_name": price_performance_source_name(market_source),
                "data_time": as_of,
                "period_or_basis": "前复权收盘价 5/20/60/120 个交易日收益率",
                "verification_status": verification_status(market_source),
                "missing_behavior": "缺失时短期收益率字段写来源缺失，不得写成未来收益判断",
            },
            {
                "file": "market_snapshot.csv",
                "field_group": "spot_indicators",
                "source_type": "public_market_data",
                "source_name": spot_indicators_source_name(market_source),
                "data_time": as_of,
                "period_or_basis": "量比和振幅实时快照",
                "verification_status": verification_status(market_source),
                "missing_behavior": "缺失时量比和振幅字段写来源缺失，不得自行计算",
            },
            {
                "file": "market_snapshot.csv",
                "field_group": "ps_ttm",
                "source_type": "public_market_data",
                "source_name": "fixture ps_ttm"
                if market_source == "fixture"
                else "AkShare stock_value_em",
                "data_time": as_of,
                "period_or_basis": "市销率 PS(TTM)，输出列为 ps_ttm",
                "verification_status": verification_status(market_source),
                "missing_behavior": "缺失时 ps_ttm 写来源缺失，不得用市值和收入自行估算",
            },
            {
                "file": "financial_summary.csv",
                "source_type": "public_market_data",
                "source_name": source_name(financial_source, "financial_summary"),
                "data_time": as_of,
                "period_or_basis": "公开财务摘要",
                "verification_status": verification_status(financial_source),
                "missing_behavior": "缺失时财务和质量字段写来源缺失或口径不可比",
            },
        ]
    }
    (output_dir / "source_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_fetch_errors(output_dir: Path, errors: list[dict[str, str]]) -> None:
    write_csv(output_dir / "fetch_errors.csv", errors, ERROR_COLUMNS)


def copy_peer_universe_if_needed(peer_universe: Path, output_dir: Path) -> None:
    destination = output_dir / "peer_universe.csv"
    if peer_universe.resolve() == destination.resolve():
        return
    shutil.copyfile(peer_universe, destination)


def run_pipeline(args: argparse.Namespace) -> int:
    peer_universe = Path(args.peer_universe)
    output_dir = Path(args.output_dir)
    log_step(
        f"pipeline start: peer_universe={peer_universe} output_dir={output_dir} "
        f"market_source={args.market_source} financial_source={args.financial_source}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    peers = read_peer_universe(peer_universe)
    log_step(f"loaded peer universe: peers={len(peers)}")
    copy_peer_universe_if_needed(peer_universe, output_dir)
    market_rows, market_errors = fetch_market_snapshot(
        peers,
        args.market_source,
        args.as_of,
    )
    try:
        financial_rows, financial_errors = fetch_financial_summary(
            peers,
            args.financial_source,
        )
    except FinancialSourceError as exc:
        financial_rows = exc.rows
        financial_errors = exc.errors
        log_step(f"financial source raised with preserved rows: errors={len(financial_errors)}")
    except Exception as exc:
        if args.financial_source != "akshare":
            raise
        financial_errors = [
            {
                "code": normalize_a_share_code(peer["code"]),
                "source": args.financial_source,
                "stage": "financial_summary",
                "error": str(exc),
            }
            for peer in peers
        ]
        financial_rows = [
            {column: MISSING for column in FINANCIAL_COLUMNS}
            | {"code": normalize_a_share_code(peer["code"])}
            for peer in peers
        ]
        log_step(f"financial source failed globally; degraded rows={len(financial_rows)} error={exc}")

    log_step("writing market_snapshot.csv")
    write_csv(output_dir / "market_snapshot.csv", market_rows, MARKET_COLUMNS)
    log_step("writing financial_summary.csv")
    write_csv(output_dir / "financial_summary.csv", financial_rows, FINANCIAL_COLUMNS)
    log_step("writing source_manifest.json")
    write_source_manifest(
        output_dir,
        args.as_of,
        args.market_source,
        args.financial_source,
    )
    log_step(f"writing fetch_errors.csv with {len(market_errors) + len(financial_errors)} error(s)")
    write_fetch_errors(output_dir, market_errors + financial_errors)

    print(f"wrote public data exports: {output_dir}")
    if market_errors or financial_errors:
        print(
            f"completed with {len(market_errors) + len(financial_errors)} fetch error(s)",
            file=sys.stderr,
        )
    if args.financial_source == "akshare" and financial_errors:
        return 1
    return 0


def main() -> int:
    return run_pipeline(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
