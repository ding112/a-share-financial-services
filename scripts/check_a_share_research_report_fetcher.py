#!/usr/bin/env python3
"""离线校验 A 股研报索引及其一键准备集成。"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTO_PREPARE = ROOT / "scripts/auto_prepare_a_share_research_pack.py"
FETCHER = ROOT / "scripts/fetch_a_share_research_reports.py"

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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_auto_prepare(
    output_dir: Path,
    scenario: str = "success",
    force: bool = False,
) -> subprocess.CompletedProcess[str]:
    offline_modules = output_dir.parent / "offline-modules"
    offline_modules.mkdir(parents=True, exist_ok=True)
    (offline_modules / "akshare.py").write_text(
        'raise ImportError("offline research report fixture check")\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        str(offline_modules)
        if not existing_pythonpath
        else f"{offline_modules}{os.pathsep}{existing_pythonpath}"
    )
    command = [
        sys.executable,
        str(AUTO_PREPARE),
        "--theme",
        "机器人产业链",
        "--output-dir",
        str(output_dir),
        "--as-of",
        "2026-07-13",
        "--universe-source",
        "fixture",
        "--market-source",
        "fixture",
        "--financial-source",
        "fixture",
        "--max-peers",
        "2",
        "--research-report-source",
        "fixture",
        "--research-report-fixture-scenario",
        scenario,
        "--research-report-lookback-days",
        "30",
        "--research-report-limit",
        "2",
    ]
    if force:
        command.append("--force")
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def validate_success_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir)
        if result.returncode != 0:
            errors.append(f"一键准备成功场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return

        for filename in [
            "peer_universe.csv",
            "market_snapshot.csv",
            "financial_summary.csv",
            "research_reports.csv",
            "source_manifest.json",
            "fetch_errors.csv",
        ]:
            if not (output_dir / filename).is_file():
                errors.append(f"一键准备成功场景缺少 {filename}")
        if not (output_dir / "research_reports").is_dir():
            errors.append("一键准备成功场景缺少 research_reports/ 目录")

        report_path = output_dir / "research_reports.csv"
        if not report_path.is_file():
            return
        rows = read_rows(report_path)
        if len(rows) != 4:
            errors.append(f"2 个证券、每证券上限 2 条时应输出 4 条研报，实际 {len(rows)} 条")
            return

        missing_columns = [column for column in REPORT_COLUMNS if column not in rows[0]]
        if missing_columns:
            errors.append(f"research_reports.csv 缺少列: {', '.join(missing_columns)}")
        identities = [row.get("report_id", "") for row in rows]
        if len(identities) != len(set(identities)):
            errors.append("research_reports.csv 未按稳定报告 ID 去重")
        counts_by_security: dict[str, int] = {}
        for row in rows:
            code = row.get("security_code", "")
            counts_by_security[code] = counts_by_security.get(code, 0) + 1
        if not counts_by_security or any(count != 2 for count in counts_by_security.values()):
            errors.append(f"每个证券应恰好保留上限内的 2 条研报，实际 {counts_by_security}")
        if any(
            not "2026-06-13" <= row.get("publish_date", "") <= "2026-07-13"
            for row in rows
        ):
            errors.append("research_reports.csv 包含检索窗口外的研报")
        sort_keys = [
            (row.get("publish_date", ""), row.get("report_id", ""))
            for row in rows
        ]
        expected_sort_keys = sorted(sort_keys, key=lambda item: (-int(item[0].replace("-", "")), item[1]))
        if sort_keys != expected_sort_keys:
            errors.append("research_reports.csv 未按发布日期降序、报告 ID 升序稳定排序")
        if any(row.get("scope_type") != "stock" for row in rows):
            errors.append("Issue 01 只能输出 stock 范围研报")
        if any(row.get("source_type") != "third_party" for row in rows):
            errors.append("研报索引必须统一标记为 third_party")
        if any(row.get("verification_status") != "待验证" for row in rows):
            errors.append("研报索引必须统一标记为待验证")
        if any(row.get("local_pdf_path") != "来源缺失" for row in rows):
            errors.append("Issue 01 不下载 PDF，本地路径必须为来源缺失")
        if any(
            not row.get("detail_url", "").startswith(
                "https://data.eastmoney.com/report/zw_stock.jshtml?encodeUrl="
            )
            for row in rows
        ):
            errors.append("研报详情链接必须由源记录 encodeUrl 定位，不得按报告 ID 猜测")
        financial_rows = read_rows(output_dir / "financial_summary.csv")
        if financial_rows and any(
            field in financial_rows[0]
            for field in ["rating", "profit_forecast_raw", "report_id"]
        ):
            errors.append("研报评级、预测或身份字段不得写入 financial_summary.csv")

        manifest_path = output_dir / "source_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest.get("files", [])
            by_file = {item.get("file"): item for item in files if isinstance(item, dict)}
            for filename in ["research_reports.csv", "research_reports/"]:
                if filename not in by_file:
                    errors.append(f"source_manifest.json 缺少 {filename} 条目")
            index_entry = by_file.get("research_reports.csv", {})
            for token in ["30", "2", "发布日期降序", "报告 ID"]:
                if token not in str(index_entry.get("period_or_basis", "")):
                    errors.append(f"研报索引来源口径缺少 `{token}`")
            if index_entry.get("verification_status") != "待验证":
                errors.append("研报索引来源清单必须标记为待验证")

        auto_manifest = json.loads(
            (output_dir / "auto_prepare_manifest.json").read_text(encoding="utf-8")
        )
        if auto_manifest.get("inputs", {}).get("research_report_source") != "fixture":
            errors.append("auto_prepare_manifest.json 必须记录解析后的实际研报来源")

        first_output = report_path.read_text(encoding="utf-8")
        repeated = run_auto_prepare(output_dir, force=True)
        if repeated.returncode != 0:
            errors.append(f"相同输入强制重跑退出码为 {repeated.returncode}")
        elif report_path.read_text(encoding="utf-8") != first_output:
            errors.append("相同输入重复运行产生了研报索引顺序或内容漂移")


def research_report_errors(output_dir: Path) -> list[dict[str, str]]:
    return [
        row
        for row in read_rows(output_dir / "fetch_errors.csv")
        if row.get("stage", "").startswith("research_report_index")
    ]


def run_independent_fetcher(
    output_dir: Path,
    scenario: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(FETCHER),
            "--peer-universe",
            str(output_dir / "peer_universe.csv"),
            "--output-dir",
            str(output_dir),
            "--as-of",
            "2026-07-13",
            "--source",
            "fixture",
            "--fixture-scenario",
            scenario,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def validate_no_data_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, scenario="no-data")
        if result.returncode != 0:
            errors.append(f"一键准备无数据场景退出码为 {result.returncode}")
            return
        if read_rows(output_dir / "research_reports.csv"):
            errors.append("无数据场景的 research_reports.csv 应只有稳定表头")
        stages = {row.get("stage") for row in research_report_errors(output_dir)}
        if stages != {"research_report_index_no_data"}:
            errors.append(f"无数据场景错误阶段应仅为 research_report_index_no_data，实际 {stages}")
        independent = run_independent_fetcher(output_dir, "no-data")
        if independent.returncode != 0:
            errors.append("真实无数据时独立抓取入口必须返回成功")


def validate_null_data_response_is_no_data(errors: list[str]) -> None:
    """东方财富以 data: null 表示空结果时，仍应按无数据处理。"""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peer_path = root / "peer_universe.csv"
        with peer_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["code", "name"])
            writer.writeheader()
            writer.writerow({"code": "300750.SZ", "name": "宁德时代"})

        boundary = root / "boundary"
        boundary.mkdir()
        (boundary / "sitecustomize.py").write_text(
            """\
import urllib.request


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b'{"data": null, "TotalPage": 0}'


def _urlopen(request, timeout=None):
    return _Response()


urllib.request.urlopen = _urlopen
""",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(boundary)
        output_dir = root / "output"
        result = subprocess.run(
            [
                sys.executable,
                str(FETCHER),
                "--peer-universe",
                str(peer_path),
                "--output-dir",
                str(output_dir),
                "--as-of",
                "2026-07-13",
                "--source",
                "eastmoney",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode != 0:
            errors.append("东方财富 data: null 空结果必须返回成功")
            return
        stages = {row.get("stage") for row in research_report_errors(output_dir)}
        if stages != {"research_report_index_no_data"}:
            errors.append(f"东方财富 data: null 应记录无数据，实际阶段 {stages}")


def validate_partial_failure_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, scenario="partial-failure")
        if result.returncode != 0:
            errors.append(f"一键准备部分失败场景退出码为 {result.returncode}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        if len(rows) != 2:
            errors.append(f"部分失败应保留成功证券的 2 条研报，实际 {len(rows)} 条")
        stages = [row.get("stage") for row in research_report_errors(output_dir)]
        if stages != ["research_report_index"]:
            errors.append(f"部分失败应记录一个 research_report_index，实际 {stages}")
        independent = run_independent_fetcher(output_dir, "partial-failure")
        if independent.returncode != 0:
            errors.append("部分证券失败时独立抓取入口必须返回成功")


def validate_all_failure_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, scenario="all-failure")
        if result.returncode != 0:
            errors.append(f"一键准备全部失败场景必须继续完成，实际退出码 {result.returncode}")
            return
        if "warning: fetch_a_share_research_reports.py exited 1" not in result.stderr:
            errors.append("一键准备全部失败场景未输出研报可选阶段告警")
        for filename in ["peer_universe.csv", "market_snapshot.csv", "financial_summary.csv"]:
            if not (output_dir / filename).is_file():
                errors.append(f"研报全部失败时核心数据包缺少 {filename}")
        if read_rows(output_dir / "research_reports.csv"):
            errors.append("研报全部失败时 research_reports.csv 应为空索引")
        report_errors = research_report_errors(output_dir)
        if len(report_errors) != 2 or {row.get("stage") for row in report_errors} != {
            "research_report_index"
        }:
            errors.append("研报全部失败时应为每个证券记录 research_report_index")

        independent = run_independent_fetcher(output_dir, "all-failure")
        if independent.returncode == 0:
            errors.append("所有索引请求失败时独立抓取入口必须返回非零")
        for filename in ["research_reports.csv", "source_manifest.json", "fetch_errors.csv"]:
            if not (output_dir / filename).is_file():
                errors.append(f"独立抓取器全失败返回前未写出 {filename}")


def validate_defaults_and_help(errors: list[str]) -> None:
    help_result = subprocess.run(
        [sys.executable, str(FETCHER), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if help_result.returncode != 0:
        errors.append(f"独立研报抓取入口 --help 退出码为 {help_result.returncode}")
    for token in [
        "--peer-universe",
        "--output-dir",
        "--as-of",
        "--lookback-days",
        "--limit-per-security",
    ]:
        if token not in help_result.stdout:
            errors.append(f"独立研报抓取入口 --help 缺少 {token}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peer_path = root / "peer_universe.csv"
        with peer_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["code", "name"])
            writer.writeheader()
            writer.writerow({"code": "300750.SZ", "name": "宁德时代"})
        result = subprocess.run(
            [
                sys.executable,
                str(FETCHER),
                "--peer-universe",
                str(peer_path),
                "--output-dir",
                str(root / "output"),
                "--as-of",
                "2026-07-13",
                "--source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"独立抓取器默认参数场景退出码为 {result.returncode}")
        manifest_path = root / "output" / "source_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            index_entries = [
                item
                for item in manifest.get("files", [])
                if item.get("file") == "research_reports.csv"
            ]
            basis = str(index_entries[0].get("period_or_basis", "")) if index_entries else ""
            if "730" not in basis or "20" not in basis:
                errors.append("独立抓取器默认口径必须为回溯 730 天、每证券最多 20 条")


def validate_research_report_fetcher() -> list[str]:
    errors: list[str] = []
    validate_defaults_and_help(errors)
    validate_success_scenario(errors)
    validate_no_data_scenario(errors)
    validate_null_data_response_is_no_data(errors)
    validate_partial_failure_scenario(errors)
    validate_all_failure_scenario(errors)
    return errors


def main() -> int:
    errors = validate_research_report_fetcher()
    if errors:
        print(f"FAIL - {len(errors)} 个 A 股研报索引问题:", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A 股研报索引检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
