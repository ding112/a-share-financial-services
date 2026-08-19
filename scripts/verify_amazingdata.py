#!/usr/bin/env python3
"""End-to-end verification for the China Galaxy Securities AmazingData SDK.

This script confirms the SDK can import, log in, and fetch representative
data across every data family the repo wants to map (base / market /
financial / shareholder / trading-anomaly / index / industry / treasury).
It records the real return shapes to ``.scratch/verify_amazingdata_result.json``
so later skill-contract work can cite actual field names instead of guessing.

Runtime: **Linux x64 or Windows x64 only.** The underlying ``tgw`` transport
ships no macOS binaries, so importing AmazingData on macOS raises
``ModuleNotFoundError``. That is expected; run this on the remote Linux/Windows
host that actually has network reach to the Galaxy data server.

Credentials come from the environment (or a local ``.env`` next to the repo
root), never printed:

    AD_USERNAME / AD_PASSWORD / AD_HOST / AD_PORT

Usage::

    python scripts/verify_amazingdata.py            # full probe
    python scripts/verify_amazingdata.py --quick    # login + code list + calendar only

Exit code is non-zero if any probe fails, so it can gate later integration.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import traceback
from pathlib import Path


# --- platform guard -------------------------------------------------------

def _platform_ok() -> bool:
    if sys.platform.startswith("win"):
        return platform.machine().lower() in ("amd64", "x86_64", "x64")
    if sys.platform.startswith("linux"):
        return platform.machine().lower() in ("x86_64", "amd64")
    return False


if not _platform_ok():
    print(f"[BLOCKED] AmazingData SDK only runs on Linux x64 / Windows x64.")
    print(f"         Current platform: {sys.platform} / {platform.machine()}")
    print(f"         Run this script on the remote Linux/Windows host instead.")
    sys.exit(3)


# --- env / credentials ----------------------------------------------------

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
        if k.startswith("AD_") and k not in os.environ:
            os.environ[k] = v


def need_creds() -> dict:
    missing = [k for k in ("AD_USERNAME", "AD_PASSWORD", "AD_HOST", "AD_PORT")
               if not os.environ.get(k)]
    if missing:
        print(f"[FAIL] Missing env vars: {missing}")
        print("Set AD_USERNAME / AD_PASSWORD / AD_HOST / AD_PORT "
              "(or put them in a .env next to the repo root).")
        sys.exit(2)
    return {
        "username": os.environ["AD_USERNAME"],
        "password": os.environ["AD_PASSWORD"],
        "host": os.environ["AD_HOST"],
        "port": int(os.environ["AD_PORT"]),
    }


# --- shape recorder -------------------------------------------------------

def shape(obj):
    """Record a serializable shape: DataFrame / dict-of-DataFrame / list / other."""
    try:
        import pandas as pd
    except Exception:
        pd = None
    if pd is not None and isinstance(obj, pd.DataFrame):
        return {"type": "DataFrame", "rows": int(len(obj)), "cols": int(obj.shape[1]),
                "columns": list(obj.columns)[:40]}
    if isinstance(obj, dict):
        out = {"type": "dict", "keys_count": len(obj), "sample_keys": list(obj.keys())[:5]}
        if obj and pd is not None:
            first = next(iter(obj.values()))
            if isinstance(first, pd.DataFrame):
                out["value_shape"] = {"rows": int(len(first)), "cols": int(first.shape[1]),
                                      "columns": list(first.columns)[:40]}
        return out
    if isinstance(obj, (list, tuple)):
        return {"type": type(obj).__name__, "len": len(obj), "sample": list(obj)[:5]}
    return {"type": type(obj).__name__, "repr": repr(obj)[:200]}


def run(name, fn, results, samples):
    """Run one probe, capture exceptions, never abort the whole suite."""
    try:
        ret = fn()
        results[name] = "OK"
        samples[name] = shape(ret)
        s = samples[name]
        if s.get("type") == "DataFrame":
            print(f"[OK] {name}: {s['rows']} rows x {s['cols']} cols")
        elif s.get("type") == "dict":
            v = s.get("value_shape")
            print(f"[OK] {name}: dict {s['keys_count']} keys"
                  + (f", first value {v['rows']}x{v['cols']}" if v else ""))
        elif s.get("type") in ("list", "tuple"):
            print(f"[OK] {name}: {s['len']} items")
        else:
            print(f"[OK] {name}: {s['type']}")
    except Exception as e:  # noqa: BLE001 - probe must not abort suite
        results[name] = f"ERR: {type(e).__name__}: {e}"
        samples[name] = {"error": str(e)}
        print(f"[ERR] {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)


# --- main -----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="AmazingData end-to-end verification.")
    ap.add_argument("--quick", action="store_true",
                    help="login + code list + calendar only")
    args = ap.parse_args()

    load_env_file()
    creds = need_creds()

    print("=" * 60)
    print("Step 1: import + login")
    print("=" * 60)
    try:
        import AmazingData as ad
        print(f"[OK] import AmazingData, version={getattr(ad, '__version__', '?')}")
    except Exception as e:
        print(f"[FAIL] import AmazingData: {e}")
        sys.exit(1)

    try:
        ad.login(username=creds["username"], password=creds["password"],
                 host=creds["host"], port=creds["port"])
        print("[OK] ad.login succeeded")
    except Exception as e:
        print(f"[FAIL] ad.login: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

    results: dict[str, str] = {"import": "OK", "login": "OK"}
    samples: dict[str, dict] = {}

    base = ad.BaseData()
    calendar = base.get_calendar()
    market = ad.MarketData(calendar)
    info = ad.InfoData()

    codes = ["000001.SZ", "600519.SH"]

    print("\n" + "=" * 60)
    print("Step 2: base data (BaseData)")
    print("=" * 60)
    run("base.get_calendar", lambda: base.get_calendar(), results, samples)
    run("base.get_code_list(EXTRA_STOCK_A)",
        lambda: base.get_code_list(security_type="EXTRA_STOCK_A"), results, samples)

    if args.quick:
        _finish(results, samples)
        return

    run("base.get_code_info(EXTRA_STOCK_A)",
        lambda: base.get_code_info(security_type="EXTRA_STOCK_A"), results, samples)
    run("base.get_backward_factor", lambda: base.get_backward_factor(codes), results, samples)

    print("\n" + "=" * 60)
    print("Step 3: market data (MarketData)")
    print("=" * 60)
    run("market.query_kline(day)",
        lambda: market.query_kline(code_list=codes, begin_date=20240101,
                                   end_date=20240131, period="day"), results, samples)

    print("\n" + "=" * 60)
    print("Step 4: financial statements (InfoData)")
    print("=" * 60)
    run("info.get_income", lambda: info.get_income(code_list=codes), results, samples)
    run("info.get_balance_sheet", lambda: info.get_balance_sheet(code_list=codes), results, samples)
    run("info.get_cash_flow", lambda: info.get_cash_flow(code_list=codes), results, samples)

    print("\n" + "=" * 60)
    print("Step 5: shareholder / equity / events (InfoData)")
    print("=" * 60)
    run("info.get_share_holder", lambda: info.get_share_holder(code_list=codes), results, samples)
    run("info.get_equity_structure", lambda: info.get_equity_structure(code_list=codes), results, samples)
    run("info.get_equity_restricted", lambda: info.get_equity_restricted(code_list=codes), results, samples)

    print("\n" + "=" * 60)
    print("Step 6: trading anomaly / margin (InfoData)")
    print("=" * 60)
    run("info.get_long_hu_bang", lambda: info.get_long_hu_bang(code_list=codes), results, samples)
    run("info.get_block_trading", lambda: info.get_block_trading(code_list=codes), results, samples)
    run("info.get_margin_detail", lambda: info.get_margin_detail(code_list=codes), results, samples)

    print("\n" + "=" * 60)
    print("Step 7: index / industry index / treasury (InfoData)")
    print("=" * 60)
    run("info.get_index_constituent(000300.SH)",
        lambda: info.get_index_constituent(["000300.SH"]), results, samples)
    run("info.get_industry_base_info", lambda: info.get_industry_base_info(), results, samples)
    run("info.get_treasury_yield",
        lambda: info.get_treasury_yield(["y1", "y5", "y10"]), results, samples)

    _finish(results, samples)


def _finish(results, samples):
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    ok = sum(1 for v in results.values() if v == "OK")
    err = len(results) - ok
    print(f"ok={ok} err={err} total={len(results)}")
    out = {"results": results, "samples": samples}
    Path(".scratch").mkdir(exist_ok=True)
    Path(".scratch/verify_amazingdata_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Details -> .scratch/verify_amazingdata_result.json")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
