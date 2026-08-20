#!/usr/bin/env python3
"""Thin HTTP client for the China Galaxy Securities AmazingData REST service.

The broker-side ``ad_mcp/http_server.py`` exposes the 55 AmazingData MCP tools
as plain REST endpoints (``POST /api/{tool}``, JSON body, JSON response). This
script lets a local machine (including macOS, where the AmazingData SDK has no
binaries anyway) call that service with nothing but the Python standard library.

It deliberately does NOT speak MCP, does NOT connect to the Galaxy data server
directly, and does NOT touch credentials: the login session lives on the broker
host inside the HTTP service, and the ONLY thing needed here is its reachable
base URL.

Credentials never leave the broker host. This client never sees or prints
AD_USERNAME / AD_PASSWORD.

Usage::

    python scripts/ad_http_client.py --base http://127.0.0.1:8000 --quick
    python scripts/ad_http_client.py --tool mcp_calendar '{"market":"SH"}'
    AD_HTTP_BASE=http://192.168.1.20:8000 python scripts/ad_http_client.py \\
        --tool mcp_kline '{"code_list":["000001.SZ"],"begin_date":20240102,"end_date":20240105}'

Base URL resolution order:
    1. ``--base`` argument
    2. ``AD_HTTP_BASE`` environment variable
    3. ``AD_HTTP_HOST`` + ``AD_HTTP_PORT`` environment variables
    4. "http://127.0.0.1:8000"

Exit code is 0 on success (and on a ``--quick`` smoke that is fully OK),
non-zero on network / HTTP / business errors, so it can gate integration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


# --- config ----------------------------------------------------------------

def load_env_file(path: str = ".env") -> None:
    """Load AD_* vars from a local .env into os.environ (never overwrite)."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("AD_HTTP_BASE", "AD_HTTP_HOST", "AD_HTTP_PORT") and k not in os.environ:
            os.environ[k] = v


def resolve_base(arg_base: str | None) -> str:
    base = arg_base or os.environ.get("AD_HTTP_BASE")
    if base:
        return base.rstrip("/")
    host = os.environ.get("AD_HTTP_HOST", "127.0.0.1")
    port = os.environ.get("AD_HTTP_PORT", "8000")
    return f"http://{host}:{port}"


def _ensure_sane(value, key):
    if isinstance(value, dict):
        return {k: _ensure_sane(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_ensure_sane(v, key) for v in value]
    return value


# --- transport -------------------------------------------------------------

class AdHttpError(RuntimeError):
    """Carries the service's structured error fields when present."""

    def __init__(self, message, *, context=None, error_type=None, suggestion=None,
                 status=None):
        super().__init__(message)
        self.context = context
        self.error_type = error_type
        self.suggestion = suggestion
        self.status = status


class AdHttpClient:
    def __init__(self, base: str, timeout: float = 60.0, capture_dir: str | None = None):
        self.base = base.rstrip("/")
        self.timeout = timeout
        # When set, dump raw request + response (incl. HTTP status and body)
        # for every failing call to <capture_dir>/<tool>.<n>.json for troubleshooting.
        self.capture_dir = Path(capture_dir) if capture_dir else None

    def health(self) -> dict:
        with urllib.request.urlopen(self.base + "/", timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def tools(self) -> list[str]:
        with urllib.request.urlopen(self.base + "/tools", timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, list):
            return data
        # tolerate {"tools": [...]} shapes
        for key in ("tools", "tool_names", "names"):
            if isinstance(data.get(key), list):
                return data[key]
        raise AdHttpError("无法解析 /tools 返回结构", status=200)

    def call(self, tool: str, **params) -> dict:
        """POST /api/{tool} and return the JSON response.

        Returns the raw response dict. Raises AdHttpError on:
          - HTTP 4xx/5xx (param type error, unknown tool, crash)
          - business failure (HTTP 200 with "success": false)
        """
        url = f"{self.base}/api/{tool}"
        body = json.dumps(_ensure_sane(params, tool)).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = json.loads(r.read().decode("utf-8"))
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                payload = {"detail": e.reason or str(e)}
            self._capture_failure(tool, url, body, status, payload)
            raise self._http_failure(tool, payload, status) from e
        except urllib.error.URLError as e:
            self._capture_failure(tool, url, body, "url_error", {"detail": str(e.reason)})
            raise AdHttpError(f"无法连接 AmazingData HTTP 服务 {self.base}: {e.reason}") from e

        if isinstance(payload, dict) and payload.get("success") is False:
            self._capture_failure(tool, url, body, status, payload)
            raise self._http_failure(tool, payload, status)
        return payload

    def _capture_failure(self, tool, url, body, status, payload) -> None:
        """Persist raw request/response for a failed call for offline diagnosis.

        Writes two artifacts under capture_dir:
          - <tool>.<n>.json   per-call record
          - failures.json     append-only combined list of all failures
        """
        if not self.capture_dir:
            return
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        while (self.capture_dir / f"{tool}.{n}.json").exists():
            n += 1
        record = {
            "tool": tool,
            "url": url,
            "status": status,
            "request_body": body.decode("utf-8", errors="replace"),
            "response": payload,
        }
        (self.capture_dir / f"{tool}.{n}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        combined = self.capture_dir / "failures.json"
        try:
            existing = json.loads(combined.read_text(encoding="utf-8")) if combined.exists() else []
            if not isinstance(existing, list):
                existing = []
        except (OSError, json.JSONDecodeError):
            existing = []
        existing.append(record)
        combined.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _http_failure(tool, payload, status):
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("message") or str(payload)
            return AdHttpError(
                f"工具 {tool} 调用失败 (HTTP {status}): {detail}",
                context=payload.get("context"),
                error_type=payload.get("error_type") or payload.get("error") or
                (f"http_{status}" if status != 200 else "business_failure"),
                suggestion=payload.get("suggestion"),
                status=status)
        return AdHttpError(f"工具 {tool} 调用失败 (HTTP {status}): {payload}", status=status)


# --- smoke test ------------------------------------------------------------

def _row_count(resp: dict) -> str:
    """Best-effort human size summary of a tool response."""
    if isinstance(resp, dict):
        if isinstance(resp.get("data"), dict):
            inner = resp["data"]
            if inner and isinstance(next(iter(inner.values())), list):
                total = sum(len(v) if isinstance(v, list) else 0 for v in inner.values())
                return f"dict[{len(inner)} keys, ~{total} rows]"
        if isinstance(resp.get("data"), list):
            return f"list[{len(resp['data'])} rows]"
        if isinstance(resp.get("calendar"), list):
            return f"calendar[{len(resp['calendar'])} days]"
        if isinstance(resp.get("summary"), dict):
            return f"summary{resp['summary']}"
    return "ok"


def run_quick(client: AdHttpClient) -> int:
    """Smoke: health + code list + calendar + kline + income."""
    failures: list[str] = []

    def step(name, why_not=""):
        return lambda exc: failures.append(f"{name}: {exc}" + (f" ({why_not})" if why_not else ""))

    print("=" * 60)
    print("Smoke 1/5  health (GET /)")
    print("=" * 60)
    try:
        h = client.health()
        print(f"[OK] service={h.get('service')} logged_in={h.get('logged_in')} "
              f"tools={h.get('tool_count')}")
        if h.get("logged_in") is not True:
            print("[WARN] logged_in=false: 检查 PC 上 .env 四项凭证或重启服务")
    except Exception as e:
        print(f"[ERR] health: {e}")
        failures.append(f"health: {e}")

    print("\n" + "=" * 60)
    print("Smoke 2/5  code list (mcp_code_list EXTRA_STOCK_A)")
    print("=" * 60)
    _probe(client, "mcp_code_list", {"security_type": "EXTRA_STOCK_A"}, failures, step("code_list"))

    print("\n" + "=" * 60)
    print("Smoke 3/5  calendar (mcp_calendar SH)")
    print("=" * 60)
    _probe(client, "mcp_calendar", {"market": "SH"}, failures, step("calendar"))

    print("\n" + "=" * 60)
    print("Smoke 4/5  kline (mcp_kline 000001.SZ 2024-01)")
    print("=" * 60)
    _probe(client, "mcp_kline",
           {"code_list": ["000001.SZ"], "begin_date": 20240102, "end_date": 20240131,
            "period": "day", "limit": 10},
           failures, step("kline"))

    print("\n" + "=" * 60)
    print("Smoke 5/5  income (mcp_income 000001.SZ)")
    print("=" * 60)
    _probe(client, "mcp_income",
           {"code_list": ["000001.SZ"], "begin_date": 20230101, "end_date": 20231231},
           failures, step("income"))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    if failures:
        for f in failures:
            print(f"[FAIL] {f}")
        print(f"smoke failed: {len(failures)} error(s)")
        return 1
    print("smoke OK: health / code_list / calendar / kline / income 全部通过")
    return 0


def _probe(client, tool, params, failures, on_error):
    try:
        resp = client.call(tool, **params)
        print(f"[OK] {tool}: {_row_count(resp)}")
    except Exception as e:
        print(f"[ERR] {tool}: {e}")
        failures.append(f"{tool}: {e}")


# --- CLI -------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Call the AmazingData REST service (POST /api/{tool}).")
    ap.add_argument("--base", help="e.g. http://127.0.0.1:8000 (or AD_HTTP_BASE)")
    ap.add_argument("--timeout", type=float, default=60.0, help="request timeout seconds")
    ap.add_argument("--quick", action="store_true",
                    help="run the 5-probe smoke suite (health/code_list/calendar/kline/income)")
    ap.add_argument("--tools", action="store_true", help="list available tool names")
    ap.add_argument("--health", action="store_true", help="print service health JSON")
    ap.add_argument("--tool", help="tool name, e.g. mcp_kline")
    ap.add_argument("params", nargs="?", help='JSON parameter object, e.g. \'{"market":"SH"}\'')
    args = ap.parse_args()

    load_env_file()
    base = resolve_base(args.base)
    client = AdHttpClient(base, timeout=args.timeout)

    try:
        if args.health:
            return _ok(json.dumps(client.health(), ensure_ascii=False, indent=2))

        if args.tools:
            names = client.tools()
            print(f"{len(names)} tools:")
            for n in names:
                print(f"  {n}")
            return 0

        if args.quick:
            print(f"base = {base}")
            return run_quick(client)

        if args.tool:
            params = {}
            if args.params:
                try:
                    params = json.loads(args.params)
                except json.JSONDecodeError as e:
                    print(f"[ERR] params 不是合法 JSON: {e}")
                    return 2
                if not isinstance(params, dict):
                    print("[ERR] params 必须是 JSON 对象")
                    return 2
            resp = client.call(args.tool, **params)
            print(json.dumps(resp, ensure_ascii=False, indent=2))
            return 0

        ap.print_help()
        return 2
    except AdHttpError as e:
        _report_error(e)
        return 1
    except Exception as e:  # noqa: BLE001 - CLI should fail cleanly
        print(f"[ERR] {type(e).__name__}: {e}")
        return 1


def _report_error(e: AdHttpError) -> None:
    print(f"[ERR] {e}")
    if e.context:
        print(f"      context: {e.context}")
    if e.error_type:
        print(f"      error_type: {e.error_type}")
    if e.suggestion:
        print(f"      suggestion: {e.suggestion}")


def _ok(text: str) -> int:
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
