#!/usr/bin/env python3
"""Fetch public A-share market snapshot and financial summary data."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MISSING = "来源缺失"
USER_AGENT = "Mozilla/5.0 a-share-market-researcher/0.1"

MARKET_COLUMNS = [
    "code",
    "price",
    "pct_change",
    "amount",
    "turnover_rate",
    "market_cap",
    "float_market_cap",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "return_5d",
    "return_20d",
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
            "return_basis": MISSING,
        }

    latest_date, latest_close = closes[-1]
    result = {
        "return_5d": MISSING,
        "return_20d": MISSING,
        "return_basis": MISSING,
    }
    if len(closes) >= 6 and closes[-6][1] != 0:
        result["return_5d"] = format_percent((latest_close / closes[-6][1] - 1) * 100)
    if len(closes) >= 21 and closes[-21][1] != 0:
        result["return_20d"] = format_percent((latest_close / closes[-21][1] - 1) * 100)
    if result["return_5d"] != MISSING or result["return_20d"] != MISSING:
        result["return_basis"] = f"AkShare 前复权收盘价，截至 {latest_date}"
    return result


def akshare_date_window(as_of: str) -> tuple[str, str]:
    try:
        end_date = dt.date.fromisoformat(as_of[:10])
    except ValueError:
        end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=120)
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def fetch_akshare_price_performance(code: str, as_of: str) -> dict[str, str]:
    import akshare as ak  # type: ignore[import-not-found]

    symbol = normalize_a_share_code(code).split(".", 1)[0]
    start_date, end_date = akshare_date_window(as_of)
    frame = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
    )
    return calculate_price_performance(frame.to_dict("records"))


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
        "market_cap": clean_value(payload.get("f116")),
        "float_market_cap": clean_value(payload.get("f117")),
        "pe_ttm": clean_value(payload.get("f162") or payload.get("f167")),
        "pb": MISSING,
        "ps_ttm": MISSING,
        "return_5d": MISSING,
        "return_20d": MISSING,
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
        "market_cap": yuan_from_yi(fields[45]),
        "float_market_cap": yuan_from_yi(fields[44]),
        "pe_ttm": clean_value(fields[52]),
        "pb": clean_value(fields[46]),
        "ps_ttm": MISSING,
        "return_5d": MISSING,
        "return_20d": MISSING,
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
        "market_cap": str(10000000000 + numeric_tail * 1000000),
        "float_market_cap": str(8000000000 + numeric_tail * 1000000),
        "pe_ttm": f"{20 + numeric_tail / 10:.2f}",
        "pb": f"{2 + numeric_tail / 100:.2f}",
        "ps_ttm": f"{4 + numeric_tail / 100:.2f}",
        "return_5d": format_percent(numeric_tail / 10),
        "return_20d": format_percent(numeric_tail / 4),
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
    for peer in peers:
        code = normalize_a_share_code(peer["code"])
        try:
            if source == "fixture":
                rows.append(fixture_market_row(code, as_of))
            elif source == "tencent":
                row = fetch_tencent_market_row(code, as_of)
                try:
                    row.update(fetch_akshare_price_performance(code, as_of))
                except Exception as exc:
                    errors.append(
                        {
                            "code": code,
                            "source": "akshare",
                            "stage": "price_performance",
                            "error": str(exc),
                        }
                    )
                rows.append(row)
            else:
                row = fetch_eastmoney_market_row(code, as_of)
                try:
                    row.update(fetch_akshare_price_performance(code, as_of))
                except Exception as exc:
                    errors.append(
                        {
                            "code": code,
                            "source": "akshare",
                            "stage": "price_performance",
                            "error": str(exc),
                        }
                    )
                rows.append(row)
        except Exception as exc:
            errors.append(
                {
                    "code": code,
                    "source": source,
                    "stage": "market_snapshot",
                    "error": str(exc),
                }
            )
            rows.append(
                {
                    "code": code,
                    "price": MISSING,
                    "pct_change": MISSING,
                    "amount": MISSING,
                    "turnover_rate": MISSING,
                    "market_cap": MISSING,
                    "float_market_cap": MISSING,
                    "pe_ttm": MISSING,
                    "pb": MISSING,
                    "ps_ttm": MISSING,
                    "return_5d": MISSING,
                    "return_20d": MISSING,
                    "return_basis": MISSING,
                    "snapshot_time": as_of,
                    "basis": "抓取失败，字段降级为来源缺失",
                }
            )
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
        frame = ak.stock_financial_abstract(stock=symbol)
    except TypeError:
        frame = ak.stock_financial_abstract(symbol=symbol)
    return map_akshare_financial_summary(code, frame.to_dict("records"))


def fetch_financial_summary(
    peers: list[dict[str, str]],
    source: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for peer in peers:
        code = normalize_a_share_code(peer["code"])
        try:
            if source == "fixture":
                rows.append(fixture_financial_row(code))
            elif source == "eastmoney":
                rows.append(fetch_eastmoney_financial_row(code))
            else:
                rows.append(fetch_akshare_financial_row(code))
        except Exception as exc:
            errors.append(
                {
                    "code": code,
                    "source": source,
                    "stage": "financial_summary",
                    "error": str(exc),
                }
            )
            if source == "akshare":
                rows.append({column: MISSING for column in FINANCIAL_COLUMNS} | {"code": code})
                continue
            rows.append({column: MISSING for column in FINANCIAL_COLUMNS} | {"code": code})
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
                "source_name": source_name("fixture", "price_performance")
                if market_source == "fixture"
                else "AkShare stock_zh_a_hist",
                "data_time": as_of,
                "period_or_basis": "前复权收盘价 5/20 个交易日收益率",
                "verification_status": verification_status(market_source),
                "missing_behavior": "缺失时短期收益率字段写来源缺失，不得写成未来收益判断",
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


def run_pipeline(args: argparse.Namespace) -> int:
    peer_universe = Path(args.peer_universe)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    peers = read_peer_universe(peer_universe)
    shutil.copyfile(peer_universe, output_dir / "peer_universe.csv")
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

    write_csv(output_dir / "market_snapshot.csv", market_rows, MARKET_COLUMNS)
    write_csv(output_dir / "financial_summary.csv", financial_rows, FINANCIAL_COLUMNS)
    write_source_manifest(
        output_dir,
        args.as_of,
        args.market_source,
        args.financial_source,
    )
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
