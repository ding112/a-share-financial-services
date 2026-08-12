#!/usr/bin/env python3
"""为 A 股 research-pack 抓取东方财富个股/显式行业研报索引和限量 PDF。

东方财富端点与字段映射参考了 Apache-2.0 项目 ``a-stock-data`` 和项目现有
AkShare 目录；本实现使用标准库重新实现，并以本项目的来源、错误和输出契约
为准。PDF 只表示材料已定位，不会升级第三方证据的验证状态。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MISSING = "来源缺失"
SOURCE_NAME = "东方财富研报"
SOURCE_KEY = "eastmoney_research_report"
REPORT_API = "https://reportapi.eastmoney.com/report/list"
DETAIL_URL_TEMPLATE = "https://data.eastmoney.com/report/zw_stock.jshtml?encodeUrl={encoded_url}"
INDUSTRY_DETAIL_URL_TEMPLATE = (
    "https://data.eastmoney.com/report/zw_industry.jshtml?encodeUrl={encoded_url}"
)
PDF_URL_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{report_id}_1.pdf"
USER_AGENT = "Mozilla/5.0 a-share-market-researcher/0.1"
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_RETRY_ATTEMPTS = 3
REQUEST_RETRY_DELAY_SECONDS = 0.6
REQUEST_INTERVAL_SECONDS = 1.1
PDF_MIN_BYTES = 1024
PDF_MAX_BYTES = 50 * 1024 * 1024
PDF_TITLE_MAX_CHARS = 72

REPORT_COLUMNS = [
    "report_id",
    "scope_type",
    "security_code",
    "security_name",
    "industry_code",
    "industry_name",
    "title",
    "institution",
    "publish_date",
    "report_type",
    "rating",
    "profit_forecast_raw",
    "detail_url",
    "pdf_url",
    "local_pdf_path",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]

ERROR_COLUMNS = ["code", "source", "stage", "error"]
FORECAST_FIELDS = [
    "predictLastYearEps",
    "predictLastYearPe",
    "predictThisYearEps",
    "predictThisYearPe",
    "predictNextYearEps",
    "predictNextYearPe",
    "predictNextTwoYearEps",
    "predictNextTwoYearPe",
]

_last_request_at = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="包含 A 股股票池的 CSV。")
    parser.add_argument("--output-dir", required=True, help="research-pack 输出目录。")
    parser.add_argument("--as-of", required=True, help="检索截止日，例如 2026-07-13。")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=730,
        help="截至 as-of 的回溯天数，默认 730。",
    )
    parser.add_argument(
        "--limit-per-security",
        type=int,
        default=20,
        help="每个证券或显式行业最多保留的研报数，默认 20。",
    )
    parser.add_argument(
        "--pdf-limit-per-security",
        type=int,
        default=3,
        help="每个证券或显式行业最多下载的最新 PDF 数，默认 3。",
    )
    parser.add_argument(
        "--skip-pdf-download",
        action="store_true",
        help="跳过 PDF 下载，但仍生成研报索引和稳定材料目录。",
    )
    parser.add_argument(
        "--industry-code",
        action="append",
        default=[],
        help="显式东方财富行业代码；可重复提供，不提供时不请求行业研报。",
    )
    parser.add_argument(
        "--source",
        choices=["eastmoney", "fixture"],
        default="eastmoney",
        help="研报索引来源；fixture 仅用于离线检查。",
    )
    parser.add_argument(
        "--fixture-scenario",
        choices=[
            "success",
            "no-data",
            "partial-failure",
            "all-failure",
            "pdf-partial-failure",
            "pdf-non-pdf",
            "industry-no-data",
            "industry-partial-failure",
            "shared-report",
        ],
        default="success",
        help="fixture 离线场景。",
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


def read_peer_universe(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty peer universe: {path}")
    if any(not row.get("code", "").strip() for row in rows):
        raise ValueError(f"peer universe requires non-empty code column: {path}")
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_as_of(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def search_window(as_of: str, lookback_days: int) -> tuple[dt.date, dt.date]:
    end = parse_as_of(as_of)
    return end - dt.timedelta(days=lookback_days), end


def _throttle_request() -> None:
    global _last_request_at
    wait_seconds = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def request_json(params: dict[str, str]) -> dict[str, Any]:
    """串行、超时且有限重试地请求东方财富公开研报端点。"""

    global _last_request_at
    url = f"{REPORT_API}?{urllib.parse.urlencode(params)}"
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
                raise ValueError("Eastmoney report response must be a JSON object")
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
    raise RuntimeError(f"Eastmoney report request failed after retries: {last_error}")


def fetch_eastmoney_index(
    peer: dict[str, str],
    begin_date: dt.date,
    end_date: dt.date,
    limit_per_security: int,
) -> list[dict[str, Any]]:
    symbol = normalize_a_share_code(peer["code"]).split(".", 1)[0]
    page_size = min(500, max(100, limit_per_security * 2))
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {
            "industryCode": "*",
            "pageSize": str(page_size),
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": begin_date.isoformat(),
            "endTime": end_date.isoformat(),
            "pageNo": str(page),
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": symbol,
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        payload = request_json(params)
        page_rows = payload.get("data")
        if page_rows is None:
            page_rows = []
        elif not isinstance(page_rows, list):
            raise ValueError("Eastmoney report response missing data array")
        if not page_rows:
            break
        if any(not isinstance(row, dict) for row in page_rows):
            raise ValueError("Eastmoney report response contains non-object records")
        records.extend(page_rows)
        total_pages = int(payload.get("TotalPage") or 1)
        if page >= total_pages or len(records) >= limit_per_security * 2:
            break
        page += 1
    return records


def fetch_eastmoney_industry_index(
    industry_code: str,
    begin_date: dt.date,
    end_date: dt.date,
    limit_per_industry: int,
) -> list[dict[str, Any]]:
    page_size = min(500, max(100, limit_per_industry * 2))
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {
            "industryCode": industry_code,
            "pageSize": str(page_size),
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": begin_date.isoformat(),
            "endTime": end_date.isoformat(),
            "pageNo": str(page),
            "fields": "",
            "qType": "1",
            "orgCode": "",
            "code": "",
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        payload = request_json(params)
        page_rows = payload.get("data")
        if page_rows is None:
            page_rows = []
        elif not isinstance(page_rows, list):
            raise ValueError("Eastmoney industry report response missing data array")
        if not page_rows:
            break
        if any(not isinstance(row, dict) for row in page_rows):
            raise ValueError("Eastmoney industry report response contains non-object records")
        records.extend(page_rows)
        total_pages = int(payload.get("TotalPage") or 1)
        if page >= total_pages or len(records) >= limit_per_industry * 2:
            break
        page += 1
    return records


def fixture_index(
    peer: dict[str, str],
    as_of: dt.date,
    lookback_days: int,
    scenario: str,
    peer_index: int,
) -> list[dict[str, Any]]:
    if scenario == "all-failure" or (scenario == "partial-failure" and peer_index == 0):
        raise RuntimeError("fixture research report index failure")
    if scenario == "no-data":
        return []

    code = normalize_a_share_code(peer["code"])
    symbol = code.split(".", 1)[0]
    name = peer.get("name") or code
    newest_date = (as_of - dt.timedelta(days=1)).isoformat()
    older_date = (as_of - dt.timedelta(days=2)).isoformat()
    outside_date = (as_of - dt.timedelta(days=lookback_days + 1)).isoformat()

    def record(suffix: str, publish_date: str) -> dict[str, Any]:
        title = f"{name} fixture 研报 {suffix}"
        if suffix == "A":
            title = f"../{name}?策略:*<>|\\" + "超长标题" * 40
        return {
            "infoCode": f"AP{as_of.strftime('%Y%m%d')}{symbol}{suffix}",
            "stockCode": symbol,
            "stockName": name,
            "title": title,
            "orgSName": "fixture 券商",
            "publishDate": publish_date,
            "reportType": "公司研究",
            "emRatingName": "增持",
            "predictThisYearEps": "1.00",
            "predictNextYearEps": "1.20",
            "predictNextTwoYearEps": "1.40",
            "indvInduCode": f"fixture-industry-{suffix}",
            "indvInduName": "fixture 行业",
            "encodeUrl": f"fixture-{symbol}-{suffix}",
        }

    duplicate = record("B", newest_date)
    return [
        duplicate,
        record("A", newest_date),
        record("C", older_date),
        dict(duplicate),
        record("OLD", outside_date),
    ]


def fixture_industry_index(
    industry_code: str,
    as_of: dt.date,
    lookback_days: int,
    scenario: str,
    industry_index: int,
) -> list[dict[str, Any]]:
    if scenario == "all-failure":
        raise RuntimeError("fixture industry research report index failure")
    if scenario == "industry-partial-failure" and industry_index == 0:
        raise RuntimeError("fixture industry research report index failure")
    if scenario == "industry-no-data":
        return []

    newest_date = (as_of - dt.timedelta(days=1)).isoformat()
    older_date = (as_of - dt.timedelta(days=2)).isoformat()
    outside_date = (as_of - dt.timedelta(days=lookback_days + 1)).isoformat()

    def record(suffix: str, publish_date: str) -> dict[str, Any]:
        report_id = f"IP{as_of.strftime('%Y%m%d')}{industry_code}{suffix}"
        if scenario == "shared-report" and industry_index == 0 and suffix == "A":
            report_id = f"AP{as_of.strftime('%Y%m%d')}300750A"
        return {
            "infoCode": report_id,
            "industryCode": industry_code,
            "industryName": f"fixture 行业 {industry_code}",
            "title": f"fixture 行业 {industry_code} 研报 {suffix}",
            "orgSName": "fixture 券商",
            "publishDate": publish_date,
            "reportType": "行业研究",
            "emRatingName": "增持",
            "encodeUrl": f"fixture-industry-{industry_code}-{suffix}",
        }

    duplicate = record("B", newest_date)
    return [
        duplicate,
        record("A", newest_date),
        record("C", older_date),
        dict(duplicate),
        record("OLD", outside_date),
    ]


def normalize_record(
    record: dict[str, Any],
    peer: dict[str, str],
    begin_date: dt.date,
    end_date: dt.date,
    basis: str,
) -> dict[str, str] | None:
    report_id = str(record.get("infoCode") or "").strip()
    if not report_id:
        raise ValueError("research report record missing infoCode")
    publish_date = dt.date.fromisoformat(str(record.get("publishDate") or "")[:10])
    if publish_date < begin_date or publish_date > end_date:
        return None
    title = str(record.get("title") or "").strip()
    if not title:
        raise ValueError(f"research report {report_id} missing title")
    raw_detail_url = str(record.get("encodeUrl") or "").strip()
    if raw_detail_url.startswith(("http://", "https://")):
        detail_url = raw_detail_url
    elif raw_detail_url:
        detail_url = DETAIL_URL_TEMPLATE.format(
            encoded_url=urllib.parse.quote(raw_detail_url, safe="")
        )
    else:
        detail_url = MISSING
    forecast = {field: record.get(field) for field in FORECAST_FIELDS}
    return {
        "report_id": report_id,
        "scope_type": "stock",
        "security_code": normalize_a_share_code(peer["code"]),
        "security_name": str(record.get("stockName") or peer.get("name") or ""),
        "industry_code": str(record.get("indvInduCode") or ""),
        "industry_name": str(record.get("indvInduName") or ""),
        "title": title,
        "institution": str(record.get("orgSName") or ""),
        "publish_date": publish_date.isoformat(),
        "report_type": str(record.get("reportType") or ""),
        "rating": str(record.get("emRatingName") or record.get("sRatingName") or ""),
        "profit_forecast_raw": json.dumps(
            forecast,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "detail_url": detail_url,
        "pdf_url": PDF_URL_TEMPLATE.format(report_id=report_id),
        "local_pdf_path": MISSING,
        "source_type": "third_party",
        "source_name": SOURCE_NAME,
        "verification_status": "待验证",
        "basis": basis,
    }


def normalize_industry_record(
    record: dict[str, Any],
    industry_code: str,
    begin_date: dt.date,
    end_date: dt.date,
    basis: str,
) -> dict[str, str] | None:
    report_id = str(record.get("infoCode") or "").strip()
    if not report_id:
        raise ValueError("industry research report record missing infoCode")
    publish_date = dt.date.fromisoformat(str(record.get("publishDate") or "")[:10])
    if publish_date < begin_date or publish_date > end_date:
        return None
    title = str(record.get("title") or "").strip()
    if not title:
        raise ValueError(f"industry research report {report_id} missing title")
    returned_industry_code = str(record.get("industryCode") or industry_code).strip()
    if returned_industry_code != industry_code:
        raise ValueError(
            f"industry research report {report_id} returned unexpected industry code "
            f"{returned_industry_code} for {industry_code}"
        )
    raw_detail_url = str(record.get("encodeUrl") or "").strip()
    if raw_detail_url.startswith(("http://", "https://")):
        detail_url = raw_detail_url
    elif raw_detail_url:
        detail_url = INDUSTRY_DETAIL_URL_TEMPLATE.format(
            encoded_url=urllib.parse.quote(raw_detail_url, safe="")
        )
    else:
        detail_url = MISSING
    forecast = {field: record.get(field) for field in FORECAST_FIELDS}
    return {
        "report_id": report_id,
        "scope_type": "industry",
        "security_code": "",
        "security_name": "",
        "industry_code": industry_code,
        "industry_name": str(record.get("industryName") or ""),
        "title": title,
        "institution": str(record.get("orgSName") or ""),
        "publish_date": publish_date.isoformat(),
        "report_type": str(record.get("reportType") or ""),
        "rating": str(record.get("emRatingName") or record.get("sRatingName") or ""),
        "profit_forecast_raw": json.dumps(
            forecast,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "detail_url": detail_url,
        "pdf_url": PDF_URL_TEMPLATE.format(report_id=report_id),
        "local_pdf_path": MISSING,
        "source_type": "third_party",
        "source_name": SOURCE_NAME,
        "verification_status": "待验证",
        "basis": basis,
    }


def stable_sort(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            -int(row["publish_date"].replace("-", "")),
            row["report_id"],
            row["scope_type"],
            row["security_code"] or row["industry_code"],
        ),
    )


def deduplicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in stable_sort(rows):
        identity = (
            row["scope_type"],
            row["security_code"] or row["industry_code"],
            row["report_id"],
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result


def sanitize_filename_component(value: str, max_chars: int, max_bytes: int) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", normalized)
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    cleaned = cleaned[:max_chars].rstrip(" ._")
    cleaned = cleaned.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    cleaned = cleaned.rstrip(" ._")
    return cleaned or "report"


def pdf_relative_path(row: dict[str, str]) -> Path:
    report_id = sanitize_filename_component(row["report_id"], 48, 64)
    title = sanitize_filename_component(row["title"], PDF_TITLE_MAX_CHARS, 128)
    filename = f"{report_id}_{row['publish_date']}_{title}.pdf"
    return Path("research_reports") / filename


def pdf_destination(output_dir: Path, row: dict[str, str]) -> tuple[Path, str]:
    output_root = output_dir.resolve()
    material_path = output_root / "research_reports"
    if material_path.is_symlink():
        raise ValueError("研报 PDF 材料目录不能是符号链接")
    material_dir = material_path.resolve()
    if material_dir.parent != output_root:
        raise ValueError("研报 PDF 材料目录越出研究数据包")
    relative_path = pdf_relative_path(row)
    destination = material_dir / relative_path.name
    if destination.parent != material_dir:
        raise ValueError(f"研报 PDF 只能写入材料目录: {relative_path}")
    return destination, relative_path.as_posix()


def validate_pdf_payload(payload: bytes) -> None:
    if len(payload) < PDF_MIN_BYTES:
        raise ValueError(f"研报 PDF 响应过小: {len(payload)} bytes")
    if len(payload) > PDF_MAX_BYTES:
        raise ValueError(f"研报 PDF 响应过大: {len(payload)} bytes")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("研报 PDF 响应缺少 PDF 文件签名")


def valid_existing_pdf(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    size = path.stat().st_size
    if size < PDF_MIN_BYTES or size > PDF_MAX_BYTES:
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def reusable_pdf_for_report(material_dir: Path, report_id: str) -> Path | None:
    report_id_prefix = sanitize_filename_component(report_id, 48, 64) + "_"
    for candidate in sorted(material_dir.iterdir()):
        if (
            candidate.name.startswith(report_id_prefix)
            and candidate.suffix.lower() == ".pdf"
            and valid_existing_pdf(candidate)
        ):
            return candidate
    return None


def request_pdf_payload(url: str) -> bytes:
    """串行、超时且有限重试地下载一份东方财富研报 PDF。"""

    global _last_request_at
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRY_ATTEMPTS):
        _throttle_request()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://data.eastmoney.com/",
                "Accept": "application/pdf,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", None)
                if status is None and hasattr(response, "getcode"):
                    status = response.getcode()
                if status is not None and not 200 <= int(status) < 300:
                    raise RuntimeError(f"研报 PDF HTTP 状态异常: {status}")
                payload = response.read(PDF_MAX_BYTES + 1)
            validate_pdf_payload(payload)
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in retryable_statuses:
                raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            last_error = exc
        finally:
            _last_request_at = time.monotonic()
        if attempt + 1 < REQUEST_RETRY_ATTEMPTS:
            time.sleep(REQUEST_RETRY_DELAY_SECONDS * (attempt + 1))
    raise RuntimeError(f"Eastmoney report PDF request failed after retries: {last_error}")


def fixture_pdf_payload(row: dict[str, str], scenario: str) -> bytes:
    report_id = row["report_id"]
    if scenario == "pdf-partial-failure" and report_id.endswith("B"):
        raise RuntimeError("fixture research report PDF failure")
    if scenario == "pdf-non-pdf" and report_id.endswith("A"):
        return b"<html><body>fixture error page</body></html>" + b" " * PDF_MIN_BYTES
    if scenario == "pdf-non-pdf" and report_id.endswith("B"):
        return b"%PDF-1.4\n%%EOF\n"
    header = f"%PDF-1.4\n% synthetic fixture {report_id}\n".encode("utf-8")
    return header + b"0" * (PDF_MIN_BYTES - len(header)) + b"\n%%EOF\n"


def materialize_pdf(
    row: dict[str, str],
    output_dir: Path,
    source: str,
    fixture_scenario: str,
) -> str:
    destination, relative_path = pdf_destination(output_dir, row)
    if valid_existing_pdf(destination):
        return relative_path
    reusable = reusable_pdf_for_report(destination.parent, row["report_id"])
    if reusable is not None:
        return (Path("research_reports") / reusable.name).as_posix()
    if destination.exists() or destination.is_symlink():
        destination.unlink()

    if not row.get("pdf_url", "").startswith(("http://", "https://")):
        raise ValueError(f"研报 {row['report_id']} 缺少有效 PDF 链接")
    payload = (
        fixture_pdf_payload(row, fixture_scenario)
        if source == "fixture"
        else request_pdf_payload(row["pdf_url"])
    )
    validate_pdf_payload(payload)
    temporary = destination.with_suffix(destination.suffix + ".part")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    try:
        temporary.write_bytes(payload)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return relative_path


def download_selected_pdfs(
    rows: list[dict[str, str]],
    output_dir: Path,
    source: str,
    fixture_scenario: str,
    pdf_limit_per_security: int,
    skip_pdf_download: bool,
) -> list[dict[str, str]]:
    if skip_pdf_download:
        return []

    selected_counts: dict[str, int] = {}
    materialized_by_report_id: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    for row in rows:
        scope_key = f"{row['scope_type']}:{row['security_code'] or row['industry_code']}"
        selected_count = selected_counts.get(scope_key, 0)
        if selected_count >= pdf_limit_per_security:
            continue
        selected_counts[scope_key] = selected_count + 1
        reused_path = materialized_by_report_id.get(row["report_id"])
        if reused_path:
            row["local_pdf_path"] = reused_path
            continue
        try:
            row["local_pdf_path"] = materialize_pdf(
                row,
                output_dir,
                source,
                fixture_scenario,
            )
            materialized_by_report_id[row["report_id"]] = row["local_pdf_path"]
        except Exception as exc:
            row["local_pdf_path"] = MISSING
            errors.append(
                {
                    "code": row["security_code"] or row["industry_code"],
                    "source": SOURCE_KEY,
                    "stage": "research_report_pdf",
                    "error": f"{row['report_id']}: {exc}",
                }
            )
    return errors


def append_manifest_entry(files: list[dict[str, str]], entry: dict[str, str]) -> None:
    files[:] = [item for item in files if item.get("file") != entry["file"]]
    files.append(entry)


def write_source_manifest_entries(
    output_dir: Path,
    as_of: str,
    lookback_days: int,
    limit_per_security: int,
    pdf_limit_per_security: int,
    skip_pdf_download: bool,
    industry_codes: list[str],
) -> None:
    path = output_dir / "source_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"files": []}
    files = data.setdefault("files", [])
    if industry_codes:
        scope_basis = f"个股与显式行业（{','.join(industry_codes)}）"
        object_limit = f"每个证券或显式行业最多 {limit_per_security} 条"
        deduplication_basis = "按范围类型、对象标识和稳定报告 ID 去重"
        pdf_object_limit = "每个证券或显式行业"
        index_missing_behavior = (
            "无数据写 research_report_index_no_data；请求或解析失败写 research_report_index；"
            "不得用于财务摘要、行业规模、业务暴露、盈利预测、估值排序或 idea shortlist"
        )
    else:
        scope_basis = ""
        object_limit = f"每个证券最多 {limit_per_security} 条"
        deduplication_basis = "按稳定报告 ID 去重"
        pdf_object_limit = "每个证券"
        index_missing_behavior = (
            "无数据写 research_report_index_no_data；请求或解析失败写 research_report_index；"
            "不得用于财务摘要、业务暴露、估值排序或 idea shortlist"
        )
    basis = (
        f"截至 {as_of[:10]} 回溯 {lookback_days} 天；{object_limit}；"
        f"发布日期降序、报告 ID 升序；{deduplication_basis}"
    )
    if scope_basis:
        basis = f"{scope_basis}；{basis}"
    append_manifest_entry(
        files,
        {
            "file": "research_reports.csv",
            "source_type": "third_party",
            "source_name": SOURCE_NAME,
            "data_time": as_of[:10],
            "period_or_basis": basis,
            "verification_status": "待验证",
            "missing_behavior": index_missing_behavior,
        },
    )
    append_manifest_entry(
        files,
        {
            "file": "research_reports/",
            "source_type": "third_party",
            "source_name": "东方财富研报 PDF",
            "data_time": as_of[:10],
            "period_or_basis": (
                (f"{scope_basis}；" if scope_basis else "")
                + f"{pdf_object_limit}最多下载最新 {pdf_limit_per_security} 份 PDF；"
                f"跳过下载={'是' if skip_pdf_download else '否'}；"
                "按研报索引的发布日期降序、报告 ID 升序选择"
            ),
            "verification_status": "待验证",
            "missing_behavior": (
                "下载失败写 research_report_pdf 且 local_pdf_path 写来源缺失；"
                "PDF 只表示材料已定位，不得视为内容已验证"
            ),
        },
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_fetch_errors(output_dir: Path, errors: list[dict[str, str]]) -> None:
    path = output_dir / "fetch_errors.csv"
    existing: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = [
                row
                for row in csv.DictReader(handle)
                if not row.get("stage", "").startswith("research_report_")
            ]
    write_csv(path, existing + errors, ERROR_COLUMNS)


def run_pipeline(args: argparse.Namespace) -> int:
    if args.lookback_days < 1:
        raise ValueError("--lookback-days must be positive")
    if args.limit_per_security < 1:
        raise ValueError("--limit-per-security must be positive")
    if args.pdf_limit_per_security < 1:
        raise ValueError("--pdf-limit-per-security must be positive")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "research_reports").mkdir(parents=True, exist_ok=True)
    peers = read_peer_universe(Path(args.peer_universe))
    industry_codes = list(dict.fromkeys(code.strip() for code in args.industry_code))
    if any(not code for code in industry_codes):
        raise ValueError("--industry-code must be non-empty")
    begin_date, end_date = search_window(args.as_of, args.lookback_days)
    basis = (
        f"截至 {end_date.isoformat()} 回溯 {args.lookback_days} 天；"
        f"每个证券最多 {args.limit_per_security} 条；第三方研报仅作待验证线索"
    )
    industry_basis = (
        f"截至 {end_date.isoformat()} 回溯 {args.lookback_days} 天；"
        f"每个显式行业最多 {args.limit_per_security} 条；第三方研报仅作待验证线索"
    )

    report_rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    failed_requests = 0
    for peer_index, peer in enumerate(peers):
        code = normalize_a_share_code(peer["code"])
        try:
            if args.source == "fixture":
                raw_rows = fixture_index(
                    peer,
                    end_date,
                    args.lookback_days,
                    args.fixture_scenario,
                    peer_index,
                )
            else:
                raw_rows = fetch_eastmoney_index(
                    peer,
                    begin_date,
                    end_date,
                    args.limit_per_security,
                )
            normalized = [
                row
                for raw_row in raw_rows
                if (row := normalize_record(raw_row, peer, begin_date, end_date, basis)) is not None
            ]
            selected = deduplicate(normalized)[: args.limit_per_security]
            if not selected:
                errors.append(
                    {
                        "code": code,
                        "source": SOURCE_KEY,
                        "stage": "research_report_index_no_data",
                        "error": (
                            f"截至 {end_date.isoformat()} 回溯 {args.lookback_days} 天未返回可用个股研报"
                        ),
                    }
                )
            report_rows.extend(selected)
        except Exception as exc:
            failed_requests += 1
            errors.append(
                {
                    "code": code,
                    "source": SOURCE_KEY,
                    "stage": "research_report_index",
                    "error": str(exc),
                }
            )

    for industry_index, industry_code in enumerate(industry_codes):
        try:
            if args.source == "fixture":
                raw_rows = fixture_industry_index(
                    industry_code,
                    end_date,
                    args.lookback_days,
                    args.fixture_scenario,
                    industry_index,
                )
            else:
                raw_rows = fetch_eastmoney_industry_index(
                    industry_code,
                    begin_date,
                    end_date,
                    args.limit_per_security,
                )
            normalized = [
                row
                for raw_row in raw_rows
                if (
                    row := normalize_industry_record(
                        raw_row,
                        industry_code,
                        begin_date,
                        end_date,
                        industry_basis,
                    )
                )
                is not None
            ]
            selected = deduplicate(normalized)[: args.limit_per_security]
            if not selected:
                errors.append(
                    {
                        "code": industry_code,
                        "source": SOURCE_KEY,
                        "stage": "research_report_index_no_data",
                        "error": (
                            f"截至 {end_date.isoformat()} 回溯 {args.lookback_days} 天"
                            "未返回可用行业研报"
                        ),
                    }
                )
            report_rows.extend(selected)
        except Exception as exc:
            failed_requests += 1
            errors.append(
                {
                    "code": industry_code,
                    "source": SOURCE_KEY,
                    "stage": "research_report_index",
                    "error": str(exc),
                }
            )

    report_rows = deduplicate(report_rows)
    errors.extend(
        download_selected_pdfs(
            report_rows,
            output_dir,
            args.source,
            args.fixture_scenario,
            args.pdf_limit_per_security,
            args.skip_pdf_download,
        )
    )
    write_csv(output_dir / "research_reports.csv", report_rows, REPORT_COLUMNS)
    write_source_manifest_entries(
        output_dir,
        args.as_of,
        args.lookback_days,
        args.limit_per_security,
        args.pdf_limit_per_security,
        args.skip_pdf_download,
        industry_codes,
    )
    write_fetch_errors(output_dir, errors)

    print(f"wrote research report index: {output_dir}")
    if errors:
        print(f"completed with {len(errors)} research report notice(s)", file=sys.stderr)
    return 1 if failed_requests == len(peers) + len(industry_codes) else 0


def main() -> int:
    return run_pipeline(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
