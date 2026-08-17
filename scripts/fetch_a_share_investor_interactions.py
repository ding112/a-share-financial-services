#!/usr/bin/env python3
"""为 A 股 research-pack 抓取交易所互动平台已回复问答。"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from a_share_security_codes import read_peer_universe

SOURCE_TYPE = "company_public_material"
VERIFICATION_STATUS = "待验证"
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_LIMIT_PER_SECURITY = 50
ERROR_COLUMNS = ["code", "source", "stage", "error"]
CNINFO_ORG_URL = "https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo"
CNINFO_QUESTION_URL = "https://irm.cninfo.com.cn/newircs/company/question"
CNINFO_DETAIL_URL = "https://irm.cninfo.com.cn/newircs/question/getQuestionDetail"
SSE_COMPANY_LOOKUP_URL = "https://sns.sseinfo.com/ajax/getCompany.do"
SSE_FEED_URL = "https://sns.sseinfo.com/ajax/userfeeds.do"
USER_AGENT = "Mozilla/5.0 a-share-market-researcher/0.1"
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_RETRY_ATTEMPTS = 3
REQUEST_RETRY_DELAY_SECONDS = 0.6
REQUEST_INTERVAL_SECONDS = 1.1
CNINFO_PAGE_SIZE = 100
SSE_PAGE_SIZE = 100
SSE_PAGE_LIMIT = 200
CNINFO_PAGE_LIMIT = 200
_last_request_at = 0.0
INTERACTION_COLUMNS = [
    "interaction_id",
    "security_code",
    "security_name",
    "platform",
    "source_record_id",
    "question",
    "answer",
    "question_time",
    "answer_time",
    "question_source",
    "answerer",
    "source_url",
    "source_type",
    "source_name",
    "verification_status",
    "basis",
]
SSE_ITEM_MARKER = re.compile(
    r'<div\s+class=["\']m_feed_item["\']\s+id=["\']item-(\d+)["\']>'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-universe", required=True, help="包含 A 股股票池的 CSV。")
    parser.add_argument("--output-dir", required=True, help="research-pack 输出目录。")
    parser.add_argument("--as-of", required=True, help="研究截止日，例如 2026-08-13。")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="截至 as-of 的回答时间回溯天数，默认 365。",
    )
    parser.add_argument(
        "--limit-per-security",
        type=int,
        default=DEFAULT_LIMIT_PER_SECURITY,
        help="每个证券最多保留的已回复问答数，默认 50。",
    )
    parser.add_argument(
        "--source",
        choices=["exchange", "fixture"],
        default="exchange",
        help="互动平台来源；fixture 仅用于离线检查。",
    )
    parser.add_argument(
        "--fixture-scenario",
        choices=[
            "success",
            "no-data",
            "future-only",
            "duplicate",
            "partial-failure",
            "all-failure",
            "malformed-cninfo-detail",
            "malformed-sse-html",
            "malformed-sse-uid",
            "tie-limit",
            "cninfo-page-duplicate",
        ],
        default="success",
        help="fixture 离线场景。",
    )
    return parser.parse_args()


def read_peers(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    peers, input_errors = read_peer_universe(path)
    errors = [
        {
            "code": code,
            "source": "investor_interaction",
            "stage": "investor_interaction_input",
            "error": message,
        }
        for code, message in input_errors
    ]
    return peers, errors


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str] = INTERACTION_COLUMNS,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def interaction_id(code: str, platform: str, source_record_id: str) -> str:
    digest = hashlib.sha256(
        "\x1f".join((code, platform, source_record_id)).encode("utf-8")
    ).hexdigest()[:24]
    return f"iq_{digest}"


def evidence_basis() -> str:
    return "仅公司回复属于公司公开材料；问题断言不构成事实；需与公告或定期报告交叉验证"


def epoch_millis_to_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        moment = dt.datetime.fromtimestamp(
            float(value) / 1000,
            tz=dt.timezone.utc,
        ).astimezone(dt.timezone(dt.timedelta(hours=8)))
    except (TypeError, ValueError, OSError):
        return ""
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def local_text_to_epoch_millis(value: str) -> int:
    moment = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=dt.timezone(dt.timedelta(hours=8))
    )
    return int(moment.timestamp() * 1000)


def normalize_cninfo_record(
    record: dict[str, Any],
    detail: dict[str, Any],
    peer: dict[str, str],
) -> dict[str, str]:
    source_record_id = str(record.get("indexId") or "").strip()
    question = str(detail.get("questionContent") or record.get("mainContent") or "").strip()
    answer = str(detail.get("replyContent") or "").strip()
    question_time = epoch_millis_to_text(
        detail.get("questionDate") or record.get("pubDate")
    )
    answer_time = epoch_millis_to_text(detail.get("replyDate"))
    if not all((source_record_id, question, answer, question_time, answer_time)):
        raise ValueError(
            f"互动易详情缺少完整已回复问答字段: {source_record_id or '来源缺失'}"
        )
    code = str(peer.get("code") or "")
    name = str(
        detail.get("shortName")
        or record.get("companyShortName")
        or peer.get("name")
        or "来源缺失"
    )
    platform = "深交所互动易"
    return {
        "interaction_id": interaction_id(code, platform, source_record_id),
        "security_code": code,
        "security_name": name,
        "platform": platform,
        "source_record_id": source_record_id,
        "question": question,
        "answer": answer,
        "question_time": question_time,
        "answer_time": answer_time,
        "question_source": {
            "2": "APP",
            "4": "网站",
            "5": "公众号",
        }.get(
            str(detail.get("questionPort") or record.get("pubClient") or ""),
            "网站",
        ),
        "answerer": str(record.get("attachedAuthor") or name),
        "source_url": (
            "https://irm.cninfo.com.cn/ircs/question/questionDetail?"
            f"questionId={source_record_id}"
        ),
        "source_type": SOURCE_TYPE,
        "source_name": platform,
        "verification_status": VERIFICATION_STATUS,
        "basis": evidence_basis(),
    }


def select_cninfo_candidates(
    candidates: list[tuple[str, dict[str, Any]]],
    limit_per_security: int,
) -> list[tuple[str, dict[str, Any]]]:
    ordered = list(candidates)
    ordered.sort(key=lambda item: str(item[1].get("indexId") or ""))
    ordered.sort(key=lambda item: item[0], reverse=True)
    selected: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for candidate in ordered:
        source_record_id = str(candidate[1].get("indexId") or "").strip()
        if not source_record_id:
            raise ValueError("互动易已回复列表记录缺少 indexId")
        if source_record_id in seen:
            continue
        seen.add(source_record_id)
        selected.append(candidate)
        if len(selected) >= limit_per_security:
            break
    return selected


def html_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split())


def parse_sse_time(value: str) -> str:
    match = re.fullmatch(
        r"\s*(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})\s*",
        html_text(value),
    )
    if not match:
        return ""
    year, month, day, hour, minute = match.groups()
    return f"{year}-{month}-{day} {hour}:{minute}:00"


def parse_sse_feed(
    payload: str,
    peer: dict[str, str],
    uid: str,
) -> list[dict[str, str]]:
    matches = list(SSE_ITEM_MARKER.finditer(payload))
    rows: list[dict[str, str]] = []
    for index, item_match in enumerate(matches):
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(payload)
        segment = payload[item_match.start():segment_end]
        text_blocks = re.findall(
            r'<div\s+class=["\']m_feed_txt["\'][^>]*>(.*?)</div>',
            segment,
            flags=re.DOTALL,
        )
        source_blocks = re.findall(
            r'<div\s+class=["\']m_feed_from["\'][^>]*>\s*'
            r'<span>(.*?)</span>.*?<a[^>]*>(.*?)</a>.*?</div>',
            segment,
            flags=re.DOTALL,
        )
        if len(text_blocks) < 2 or len(source_blocks) < 2:
            continue
        source_record_id = item_match.group(1)
        code = str(peer.get("code") or "")
        name = str(peer.get("name") or "来源缺失")
        question = html_text(text_blocks[0])
        symbol = code.split(".", 1)[0]
        question = re.sub(
            rf"^:?\s*.*?\({re.escape(symbol)}\)\s*",
            "",
            question,
            count=1,
        )
        answer = html_text(text_blocks[1])
        question_time = parse_sse_time(source_blocks[0][0])
        answer_time = parse_sse_time(source_blocks[1][0])
        answerer_match = re.search(
            r'class=["\']ansface["\'][^>]*>.*?<img[^>]*title=["\']([^"\']+)',
            segment,
            flags=re.DOTALL,
        )
        if not all((question, answer, question_time, answer_time)):
            continue
        platform = "上证e互动"
        rows.append(
            {
                "interaction_id": interaction_id(code, platform, source_record_id),
                "security_code": code,
                "security_name": name,
                "platform": platform,
                "source_record_id": source_record_id,
                "question": question,
                "answer": answer,
                "question_time": question_time,
                "answer_time": answer_time,
                "question_source": html_text(source_blocks[0][1]),
                "answerer": (
                    html.unescape(answerer_match.group(1)).strip()
                    if answerer_match
                    else name
                ),
                "source_url": (
                    "https://sns.sseinfo.com/company.do?"
                    f"uid={uid}#item-{source_record_id}"
                ),
                "source_type": SOURCE_TYPE,
                "source_name": platform,
                "verification_status": VERIFICATION_STATUS,
                "basis": evidence_basis(),
            }
        )
    return rows


def parse_sse_page(
    payload: str,
    peer: dict[str, str],
    uid: str,
) -> list[dict[str, str]]:
    rows = parse_sse_feed(payload, peer, uid)
    if rows:
        return rows
    if SSE_ITEM_MARKER.search(payload):
        raise ValueError("上证e互动问答节点缺少完整问题、回答或时间字段")
    if "m_feed_note" in payload and "暂无回复" in html_text(payload):
        return []
    raise ValueError("上证e互动响应缺少问答节点或合法空页标记")


def parse_sse_uid(payload: str) -> str:
    uid = payload.strip()
    if not re.fullmatch(r"\d+", uid):
        raise ValueError("上证e互动公司查询响应缺少数字 UID")
    return uid


def fixture_sse_html(peer: dict[str, str], uid: str, as_of: dt.date) -> str:
    code = str(peer.get("code") or "").split(".", 1)[0]
    name = str(peer.get("name") or "")
    question_time = (as_of - dt.timedelta(days=2)).strftime("%Y年%m月%d日 09:00")
    answer_time = (as_of - dt.timedelta(days=1)).strftime("%Y年%m月%d日 10:00")
    return f"""
    <div class="m_feed_item" id="item-1778445">
      <div class="m_feed_txt"><a>:{name}({code})</a>{name}的业务进展如何？</div>
      <div class="m_feed_from"><span>{question_time}</span><em>来自</em><a>Android</a></div>
      <a class="ansface"><img title="{name}"></a>
      <div class="m_feed_txt" id="m_feed_txt-1778445">相关信息请以公司公告和定期报告为准。</div>
      <div class="m_feed_from"><span>{answer_time}</span><em>来自</em><a>网站</a></div>
    </div>
    """


def fixture_cninfo_payloads(
    peer: dict[str, str],
    as_of: dt.date,
) -> tuple[dict[str, Any], dict[str, Any]]:
    question_at = f"{(as_of - dt.timedelta(days=400)).isoformat()} 09:00:00"
    answer_at = f"{(as_of - dt.timedelta(days=1)).isoformat()} 10:00:00"
    question_epoch = local_text_to_epoch_millis(question_at)
    answer_epoch = local_text_to_epoch_millis(answer_at)
    question = f"{peer.get('name', '')}的业务进展如何？"
    answer = "相关信息请以公司公告和定期报告为准。"
    return (
        {
            "indexId": "2334000000000000001",
            "mainContent": question,
            "attachedId": "2334000000000000002",
            "attachedContent": answer,
            "pubDate": question_epoch,
            "attachedPubDate": None,
            "updateDate": answer_epoch,
            "companyShortName": peer.get("name", ""),
            "pubClient": "2",
            "attachedAuthor": peer.get("name", ""),
        },
        {
            "questionContent": question,
            "replyContent": answer,
            "questionDate": question_epoch,
            "replyDate": answer_epoch,
            "shortName": peer.get("name", ""),
            "questionPort": "2",
        },
    )


def fixture_rows(peers: list[dict[str, str]], as_of: dt.date) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for peer in peers:
        code = str(peer.get("code") or "")
        if code.endswith(".SZ"):
            record, detail = fixture_cninfo_payloads(peer, as_of)
            rows.append(normalize_cninfo_record(record, detail, peer))
        elif code.endswith(".SH"):
            uid = "275524" if code == "603119.SH" else "fixture-uid"
            rows.extend(parse_sse_page(fixture_sse_html(peer, uid, as_of), peer, uid))
    return rows


def _throttle_request() -> None:
    global _last_request_at
    wait_seconds = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def request_bytes(
    url: str,
    *,
    form: dict[str, str] | None = None,
    post: bool = False,
) -> bytes:
    global _last_request_at
    data = urllib.parse.urlencode(form).encode("utf-8") if form is not None else None
    if post and data is None:
        data = b""
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, text/html, */*",
            "Referer": "https://irm.cninfo.com.cn/"
            if "cninfo.com.cn" in url
            else "https://sns.sseinfo.com/",
        },
        method="POST" if post or form is not None else "GET",
    )
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRY_ATTEMPTS):
        _throttle_request()
        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in retryable_statuses:
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        finally:
            _last_request_at = time.monotonic()
        if attempt + 1 < REQUEST_RETRY_ATTEMPTS:
            time.sleep(REQUEST_RETRY_DELAY_SECONDS * (attempt + 1))
    raise RuntimeError(f"互动平台请求在有限重试后失败: {last_error}")


def request_json(
    url: str,
    *,
    form: dict[str, str] | None = None,
    post: bool = False,
) -> dict[str, Any]:
    try:
        payload = json.loads(request_bytes(url, form=form, post=post).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("互动平台响应不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("互动平台 JSON 响应必须是对象")
    return payload


def fetch_cninfo_detail(source_record_id: str) -> dict[str, Any]:
    params = {
        "questionId": source_record_id,
        "_t": str(int(time.time())),
    }
    payload = request_json(
        f"{CNINFO_DETAIL_URL}?{urllib.parse.urlencode(params)}"
    )
    detail = payload.get("data")
    if str(payload.get("statusCode") or "") != "200" or not isinstance(detail, dict):
        raise ValueError(f"互动易详情响应无效: {source_record_id}")
    return detail


def fetch_cninfo_rows(
    peer: dict[str, str],
    begin: dt.date,
    end: dt.date,
    limit_per_security: int,
) -> list[dict[str, str]]:
    symbol = str(peer.get("code") or "").split(".", 1)[0]
    org_payload = request_json(
        f"{CNINFO_ORG_URL}?_t={int(time.time())}",
        form={"keyWord": symbol},
    )
    organizations = org_payload.get("data")
    if not isinstance(organizations, list):
        raise ValueError("互动易公司检索响应缺少 data 列表")
    organization = next(
        (
            item
            for item in organizations
            if isinstance(item, dict) and str(item.get("stockCode") or "") == symbol
        ),
        None,
    )
    if not organization or not organization.get("secid"):
        return []

    candidates: list[tuple[str, dict[str, Any]]] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        params = {
            "_t": str(int(time.time())),
            "stockcode": symbol,
            "orgId": str(organization["secid"]),
            "pageSize": str(CNINFO_PAGE_SIZE),
            "pageNum": str(page),
            "keyWord": "",
            "startDay": "",
            "endDay": end.isoformat(),
        }
        payload = request_json(
            f"{CNINFO_QUESTION_URL}?{urllib.parse.urlencode(params)}",
            post=True,
        )
        raw_rows = payload.get("rows")
        raw_total_pages = payload.get("totalPage")
        if not isinstance(raw_rows, list) or any(
            not isinstance(item, dict) for item in raw_rows
        ):
            raise ValueError("互动易问答响应缺少 rows 对象列表")
        try:
            total_pages = int(raw_total_pages)
        except (TypeError, ValueError) as exc:
            raise ValueError("互动易问答响应缺少有效 totalPage") from exc
        if total_pages > CNINFO_PAGE_LIMIT:
            raise RuntimeError(f"互动易分页超过安全上限 {CNINFO_PAGE_LIMIT}")
        for record in raw_rows:
            if not (record.get("attachedId") or record.get("attachedContent")):
                continue
            update_time = epoch_millis_to_text(record.get("updateDate"))
            if not update_time:
                raise ValueError(
                    "互动易已回复列表记录缺少有效 updateDate: "
                    f"{record.get('indexId') or '来源缺失'}"
                )
            if (
                f"{begin.isoformat()} 00:00:00"
                <= update_time
                <= f"{end.isoformat()} 23:59:59"
            ):
                candidates.append((update_time, record))
        page += 1

    rows: list[dict[str, str]] = []
    for update_time, record in select_cninfo_candidates(
        candidates,
        limit_per_security,
    ):
        source_record_id = str(record.get("indexId") or "").strip()
        detail = fetch_cninfo_detail(source_record_id)
        normalized = normalize_cninfo_record(record, detail, peer)
        if normalized["answer_time"] != update_time:
            raise ValueError(
                f"互动易列表 updateDate 与详情 replyDate 不一致: {source_record_id}"
            )
        rows.append(normalized)
    return rows


def fetch_sse_rows(
    peer: dict[str, str],
    begin: dt.date,
    end: dt.date,
    limit_per_security: int,
) -> list[dict[str, str]]:
    symbol = str(peer.get("code") or "").split(".", 1)[0]
    uid = parse_sse_uid(
        request_bytes(
            SSE_COMPANY_LOOKUP_URL,
            form={"data": symbol},
        ).decode("utf-8", errors="replace")
    )

    rows: list[dict[str, str]] = []
    for page in range(1, SSE_PAGE_LIMIT + 1):
        params = {
            "typeCode": "company",
            "type": "11",
            "pageSize": str(SSE_PAGE_SIZE),
            "uid": uid,
            "page": str(page),
        }
        payload = request_bytes(
            f"{SSE_FEED_URL}?{urllib.parse.urlencode(params)}",
            post=True,
        ).decode("utf-8", errors="replace")
        page_rows = parse_sse_page(payload, peer, uid)
        if not page_rows:
            break
        rows.extend(page_rows)
        eligible = select_rows(
            rows,
            end,
            (end - begin).days,
            limit_per_security,
        )
        if len(eligible) >= limit_per_security:
            break
        oldest_page_answer = min(row["answer_time"] for row in page_rows)
        if oldest_page_answer < f"{begin.isoformat()} 00:00:00":
            break
    else:
        raise RuntimeError(f"上证e互动分页超过安全上限 {SSE_PAGE_LIMIT}")
    return rows


def fetch_exchange_result(
    peers: list[dict[str, str]],
    begin: dt.date,
    end: dt.date,
    limit_per_security: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], int, int]:
    rows: list[dict[str, str]] = []
    notices: list[dict[str, str]] = []
    request_count = 0
    failure_count = 0
    for peer in peers:
        code = str(peer.get("code") or "")
        if code.endswith(".SZ"):
            fetch = lambda: fetch_cninfo_rows(peer, begin, end, limit_per_security)
        elif code.endswith(".SH"):
            fetch = lambda: fetch_sse_rows(peer, begin, end, limit_per_security)
        else:
            notices.append(
                {
                    "code": code,
                    "source": "investor_interaction",
                    "stage": "investor_interaction_unsupported",
                    "error": "当前仅支持深交所互动易和上证e互动",
                }
            )
            continue
        request_count += 1
        try:
            peer_rows = fetch()
        except Exception as exc:
            failure_count += 1
            notices.append(
                {
                    "code": code,
                    "source": source_key(code),
                    "stage": "investor_interaction",
                    "error": str(exc),
                }
            )
            continue
        if peer_rows:
            rows.extend(peer_rows)
        else:
            notices.append(
                {
                    "code": code,
                    "source": source_key(code),
                    "stage": "investor_interaction_no_data",
                    "error": "研究窗口内未返回已回复互动问答",
                }
            )
    return rows, notices, request_count, failure_count


def select_rows(
    rows: list[dict[str, str]],
    as_of: dt.date,
    lookback_days: int,
    limit_per_security: int,
) -> list[dict[str, str]]:
    end = f"{as_of.isoformat()} 23:59:59"
    begin = f"{(as_of - dt.timedelta(days=lookback_days)).isoformat()} 00:00:00"
    selected = [
        row
        for row in rows
        if row["question_time"]
        and row["answer_time"]
        and row["answer"]
        and row["question_time"] <= end
        and begin <= row["answer_time"] <= end
    ]
    deduped: dict[str, dict[str, str]] = {}
    for row in selected:
        deduped.setdefault(row["interaction_id"], row)
    selected = list(deduped.values())
    selected.sort(key=lambda row: row["source_record_id"])
    selected.sort(key=lambda row: row["answer_time"], reverse=True)
    limited: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    for row in selected:
        code = row["security_code"]
        if counts.get(code, 0) >= limit_per_security:
            continue
        counts[code] = counts.get(code, 0) + 1
        limited.append(row)
    limited.sort(key=lambda row: row["source_record_id"])
    limited.sort(key=lambda row: row["answer_time"], reverse=True)
    limited.sort(key=lambda row: row["security_code"])
    return limited


def update_source_manifest(
    output_dir: Path,
    as_of: dt.date,
    lookback_days: int,
    limit_per_security: int,
) -> None:
    path = output_dir / "source_manifest.json"
    data: dict[str, object] = {"files": []}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    files = data.get("files")
    if not isinstance(files, list):
        files = []
    files = [item for item in files if item.get("file") != "investor_interactions.csv"]
    files.append(
        {
            "file": "investor_interactions.csv",
            "source_type": SOURCE_TYPE,
            "source_name": "深交所互动易与上证e互动",
            "data_time": as_of.isoformat(),
            "period_or_basis": (
                f"回答时间截至 {as_of.isoformat()} 回溯 {lookback_days} 天；"
                f"每证券最多 {limit_per_security} 条已回复问答"
            ),
            "verification_status": VERIFICATION_STATUS,
            "missing_behavior": (
                "问题中的断言不构成事实；公司回复需与公告或定期报告交叉验证；"
                "缺失不得解释为公司未回复"
            ),
        }
    )
    data["files"] = files
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def retained_errors(output_dir: Path) -> list[dict[str, str]]:
    path = output_dir / "fetch_errors.csv"
    rows: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if not str(row.get("stage") or "").startswith("investor_interaction")
            ]
    return rows


def source_key(code: str) -> str:
    return "cninfo_investor_interaction" if code.endswith(".SZ") else "sse_investor_interaction"


def fixture_result(
    peers: list[dict[str, str]],
    as_of: dt.date,
    scenario: str,
    limit_per_security: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], int, int]:
    supported = [
        peer
        for peer in peers
        if str(peer.get("code") or "").endswith((".SZ", ".SH"))
    ]
    unsupported_notices = [
        {
            "code": str(peer.get("code") or ""),
            "source": "investor_interaction",
            "stage": "investor_interaction_unsupported",
            "error": "当前仅支持深交所互动易和上证e互动",
        }
        for peer in peers
        if peer not in supported
    ]
    if scenario == "success":
        return fixture_rows(supported, as_of), unsupported_notices, len(supported), 0
    if scenario == "future-only":
        rows = fixture_rows(supported, as_of)
        for row in rows:
            row["answer_time"] = f"{(as_of + dt.timedelta(days=1)).isoformat()} 10:00:00"
        return rows, unsupported_notices, len(supported), 0
    if scenario == "duplicate":
        rows = fixture_rows(supported, as_of)
        return [*rows, *[dict(row) for row in rows]], unsupported_notices, len(supported), 0
    if scenario == "tie-limit":
        rows = fixture_rows(supported, as_of)
        if rows:
            first = dict(rows[0])
            first["source_record_id"] = "200"
            first["interaction_id"] = interaction_id(
                first["security_code"], first["platform"], "200"
            )
            second = dict(first)
            second["source_record_id"] = "100"
            second["interaction_id"] = interaction_id(
                second["security_code"], second["platform"], "100"
            )
            rows = [first, second, *rows[1:]]
        return rows, unsupported_notices, len(supported), 0
    if scenario == "cninfo-page-duplicate":
        rows: list[dict[str, str]] = []
        for peer in supported:
            if not str(peer.get("code") or "").endswith(".SZ"):
                rows.extend(fixture_rows([peer], as_of))
                continue
            record, detail = fixture_cninfo_payloads(peer, as_of)
            first = dict(record)
            first["indexId"] = "100"
            duplicate = dict(first)
            second = dict(record)
            second["indexId"] = "200"
            update_time = epoch_millis_to_text(record.get("updateDate"))
            selected = select_cninfo_candidates(
                [
                    (update_time, first),
                    (update_time, duplicate),
                    (update_time, second),
                ],
                limit_per_security,
            )
            rows.extend(
                normalize_cninfo_record(candidate, detail, peer)
                for _, candidate in selected
            )
        return rows, unsupported_notices, len(supported), 0
    if scenario == "malformed-cninfo-detail":
        failed = [peer for peer in supported if str(peer.get("code") or "").endswith(".SZ")]
        succeeded = [peer for peer in supported if peer not in failed]
        notices = []
        for peer in failed:
            record, detail = fixture_cninfo_payloads(peer, as_of)
            detail["replyDate"] = None
            try:
                normalize_cninfo_record(record, detail, peer)
            except ValueError as exc:
                notices.append(
                    {
                        "code": str(peer.get("code") or ""),
                        "source": source_key(str(peer.get("code") or "")),
                        "stage": "investor_interaction",
                        "error": str(exc),
                    }
                )
        return (
            fixture_rows(succeeded, as_of),
            [*unsupported_notices, *notices],
            len(supported),
            len(failed),
        )
    if scenario == "malformed-sse-html":
        failed = [peer for peer in supported if str(peer.get("code") or "").endswith(".SH")]
        succeeded = [peer for peer in supported if peer not in failed]
        notices = []
        for peer in failed:
            try:
                parse_sse_page("<html>upstream error</html>", peer, "fixture-uid")
            except ValueError as exc:
                notices.append(
                    {
                        "code": str(peer.get("code") or ""),
                        "source": source_key(str(peer.get("code") or "")),
                        "stage": "investor_interaction",
                        "error": str(exc),
                    }
                )
        return (
            fixture_rows(succeeded, as_of),
            [*unsupported_notices, *notices],
            len(supported),
            len(failed),
        )
    if scenario == "malformed-sse-uid":
        failed = [peer for peer in supported if str(peer.get("code") or "").endswith(".SH")]
        succeeded = [peer for peer in supported if peer not in failed]
        notices = []
        for peer in failed:
            try:
                parse_sse_uid("<html>upstream error</html>")
            except ValueError as exc:
                notices.append(
                    {
                        "code": str(peer.get("code") or ""),
                        "source": source_key(str(peer.get("code") or "")),
                        "stage": "investor_interaction",
                        "error": str(exc),
                    }
                )
        return (
            fixture_rows(succeeded, as_of),
            [*unsupported_notices, *notices],
            len(supported),
            len(failed),
        )
    if scenario == "no-data":
        notices = [
            {
                "code": str(peer.get("code") or ""),
                "source": source_key(str(peer.get("code") or "")),
                "stage": "investor_interaction_no_data",
                "error": "研究窗口内未返回已回复互动问答",
            }
            for peer in supported
        ]
        return [], [*unsupported_notices, *notices], len(supported), 0
    if scenario == "partial-failure":
        failed = supported[:1]
        succeeded = supported[1:]
        notices = [
            {
                "code": str(peer.get("code") or ""),
                "source": source_key(str(peer.get("code") or "")),
                "stage": "investor_interaction",
                "error": "fixture 互动平台请求失败",
            }
            for peer in failed
        ]
        return (
            fixture_rows(succeeded, as_of),
            [*unsupported_notices, *notices],
            len(supported),
            len(failed),
        )
    notices = [
        {
            "code": str(peer.get("code") or ""),
            "source": source_key(str(peer.get("code") or "")),
            "stage": "investor_interaction",
            "error": "fixture 互动平台请求失败",
        }
        for peer in supported
    ]
    return [], [*unsupported_notices, *notices], len(supported), len(supported)


def main() -> int:
    args = parse_args()
    if args.lookback_days < 1:
        raise SystemExit("--lookback-days must be positive")
    if args.limit_per_security < 1:
        raise SystemExit("--limit-per-security must be positive")
    as_of = dt.date.fromisoformat(args.as_of[:10])
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    peers, input_notices = read_peers(Path(args.peer_universe))
    if args.source == "fixture":
        raw_rows, notices, request_count, failure_count = fixture_result(
            peers,
            as_of,
            args.fixture_scenario,
            args.limit_per_security,
        )
    else:
        raw_rows, notices, request_count, failure_count = fetch_exchange_result(
            peers,
            as_of - dt.timedelta(days=args.lookback_days),
            as_of,
            args.limit_per_security,
        )
    rows = select_rows(
        raw_rows,
        as_of,
        args.lookback_days,
        args.limit_per_security,
    )
    selected_codes = {row["security_code"] for row in rows}
    terminal_notice_codes = {
        row["code"]
        for row in notices
        if row.get("stage") in {
            "investor_interaction",
            "investor_interaction_no_data",
        }
    }
    for peer in peers:
        code = peer["code"]
        if (
            code.endswith((".SZ", ".SH"))
            and code not in selected_codes
            and code not in terminal_notice_codes
        ):
            notices.append(
                {
                    "code": code,
                    "source": source_key(code),
                    "stage": "investor_interaction_no_data",
                    "error": "研究窗口内未返回已回复互动问答",
                }
            )
    write_csv(output_dir / "investor_interactions.csv", rows)
    update_source_manifest(output_dir, as_of, args.lookback_days, args.limit_per_security)
    write_csv(
        output_dir / "fetch_errors.csv",
        [*retained_errors(output_dir), *input_notices, *notices],
        ERROR_COLUMNS,
    )
    if not peers:
        return 1
    return 1 if request_count > 0 and failure_count == request_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
