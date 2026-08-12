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
    pdf_limit: int | None = 1,
    index_limit: int = 2,
    skip_pdf_download: bool = False,
    industry_codes: list[str] | None = None,
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
        str(index_limit),
    ]
    if pdf_limit is not None:
        command.extend(["--research-report-pdf-limit", str(pdf_limit)])
    if force:
        command.append("--force")
    if skip_pdf_download:
        command.append("--skip-research-report-pdf-download")
    for industry_code in industry_codes or []:
        command.extend(["--research-report-industry-code", industry_code])
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
        downloaded_by_security: dict[str, int] = {}
        downloaded_rows: list[dict[str, str]] = []
        for row in rows:
            local_path = row.get("local_pdf_path", "")
            if local_path == "来源缺失":
                continue
            downloaded_rows.append(row)
            code = row.get("security_code", "")
            downloaded_by_security[code] = downloaded_by_security.get(code, 0) + 1
            relative_path = Path(local_path)
            pdf_path = output_dir / local_path
            if not pdf_path.is_file() or not pdf_path.read_bytes().startswith(b"%PDF-"):
                errors.append(f"索引中的研报 PDF 路径无效: {local_path}")
            if (
                relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.parent != Path("research_reports")
                or any(char in relative_path.name for char in '<>:"/\\|?*')
                or len(relative_path.name.encode("utf-8")) > 240
            ):
                errors.append(f"研报 PDF 路径或文件名不安全: {local_path}")
            if row.get("report_id", "") not in relative_path.name:
                errors.append(f"研报 PDF 文件名缺少稳定报告 ID: {local_path}")
        if not downloaded_by_security or any(
            count != 1 for count in downloaded_by_security.values()
        ):
            errors.append(f"每个证券应下载最新 1 份 PDF，实际 {downloaded_by_security}")
        if any(not row.get("report_id", "").endswith("A") for row in downloaded_rows):
            errors.append("PDF 上限为 1 时必须选择索引排序中的最新稳定报告 ID")
        if not any("../" in row.get("title", "") and "?" in row.get("title", "") for row in rows):
            errors.append("成功 fixture 必须用危险且超长的原始标题验证文件名清理与截断")
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
            if "显式行业" in str(index_entry.get("period_or_basis", "")):
                errors.append("未提供行业代码时来源口径不得声称包含显式行业")
            material_entry = by_file.get("research_reports/", {})
            for token in ["1", "跳过下载=否", "发布日期降序", "报告 ID"]:
                if token not in str(material_entry.get("period_or_basis", "")):
                    errors.append(f"研报材料来源口径缺少 `{token}`")
            if (
                material_entry.get("source_type") != "third_party"
                or material_entry.get("verification_status") != "待验证"
            ):
                errors.append("研报材料来源清单必须标记为 third_party、待验证")

        auto_manifest = json.loads(
            (output_dir / "auto_prepare_manifest.json").read_text(encoding="utf-8")
        )
        if auto_manifest.get("inputs", {}).get("research_report_source") != "fixture":
            errors.append("auto_prepare_manifest.json 必须记录解析后的实际研报来源")
        if "research_report_industry_codes" in auto_manifest.get("inputs", {}):
            errors.append("未提供行业代码时一键准备清单必须保持原有个股输入形状")

        first_output = report_path.read_text(encoding="utf-8")
        reusable_path: Path | None = None
        reusable_payload = b"%PDF-1.4\n% valid reuse sentinel\n" + b"R" * 1100
        reusable_mtime: int | None = None
        if downloaded_rows:
            reusable_path = output_dir / downloaded_rows[0]["local_pdf_path"]
            reusable_path.write_bytes(reusable_payload)
            reusable_mtime = reusable_path.stat().st_mtime_ns
        repeated = run_auto_prepare(output_dir, force=True)
        if repeated.returncode != 0:
            errors.append(f"相同输入强制重跑退出码为 {repeated.returncode}")
        elif report_path.read_text(encoding="utf-8") != first_output:
            errors.append("相同输入重复运行产生了研报索引顺序或内容漂移")
        if reusable_path is not None and reusable_path.read_bytes() != reusable_payload:
            errors.append("强制刷新索引时重复下载并覆盖了既有有效 PDF")
        if reusable_path is not None and reusable_path.stat().st_mtime_ns != reusable_mtime:
            errors.append("重复运行未直接复用既有有效 PDF")


def validate_single_industry_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, industry_codes=["1238"])
        if result.returncode != 0:
            errors.append(f"单行业一键准备退出码为 {result.returncode}: {result.stderr.strip()}")
            return

        rows = read_rows(output_dir / "research_reports.csv")
        stock_rows = [row for row in rows if row.get("scope_type") == "stock"]
        industry_rows = [row for row in rows if row.get("scope_type") == "industry"]
        if len(stock_rows) != 4 or len(industry_rows) != 2:
            errors.append(
                f"单行业混合索引应包含 4 条个股和 2 条行业研报，实际 "
                f"{len(stock_rows)}/{len(industry_rows)}"
            )
        if industry_rows and any(
            row.get("industry_code") != "1238"
            or row.get("industry_name") != "fixture 行业 1238"
            or row.get("security_code")
            or row.get("security_name")
            for row in industry_rows
        ):
            errors.append("行业研报必须以显式行业代码和行业名称标识，证券字段必须留空")
        if industry_rows and any(
            row.get("source_type") != "third_party"
            or row.get("verification_status") != "待验证"
            for row in industry_rows
        ):
            errors.append("行业研报必须统一标记为 third_party、待验证")
        if industry_rows and any(
            "/report/zw_industry.jshtml?encodeUrl=" not in row.get("detail_url", "")
            for row in industry_rows
        ):
            errors.append("行业研报详情链接必须使用东方财富行业研报正文入口")

        manifest = json.loads((output_dir / "source_manifest.json").read_text(encoding="utf-8"))
        entries = {
            item.get("file"): item
            for item in manifest.get("files", [])
            if isinstance(item, dict)
        }
        for filename in ["research_reports.csv", "research_reports/"]:
            basis = str(entries.get(filename, {}).get("period_or_basis", ""))
            for token in ["个股", "显式行业", "1238"]:
                if token not in basis:
                    errors.append(f"{filename} 来源口径缺少 `{token}`")
        index_missing_behavior = str(
            entries.get("research_reports.csv", {}).get("missing_behavior", "")
        )
        for token in ["行业规模", "业务暴露", "盈利预测", "idea shortlist"]:
            if token not in index_missing_behavior:
                errors.append(f"显式行业研报缺失行为未声明禁止进入 `{token}`")
        auto_manifest = json.loads(
            (output_dir / "auto_prepare_manifest.json").read_text(encoding="utf-8")
        )
        if auto_manifest.get("inputs", {}).get("research_report_industry_codes") != ["1238"]:
            errors.append("一键准备清单必须记录显式东方财富行业代码")


def validate_industry_no_data_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(
            output_dir,
            scenario="industry-no-data",
            industry_codes=["1238"],
        )
        if result.returncode != 0:
            errors.append(f"行业无数据场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        if len(rows) != 4 or any(row.get("scope_type") != "stock" for row in rows):
            errors.append("单个行业无数据时必须保留全部成功的个股研报")
        notices = [
            row
            for row in research_report_errors(output_dir)
            if row.get("code") == "1238"
        ]
        if len(notices) != 1 or notices[0].get("stage") != "research_report_index_no_data":
            errors.append("行业无数据必须按显式行业代码记录 research_report_index_no_data")


def research_report_errors(output_dir: Path) -> list[dict[str, str]]:
    return [
        row
        for row in read_rows(output_dir / "fetch_errors.csv")
        if row.get("stage", "").startswith("research_report_index")
    ]


def research_report_pdf_errors(output_dir: Path) -> list[dict[str, str]]:
    return [
        row
        for row in read_rows(output_dir / "fetch_errors.csv")
        if row.get("stage") == "research_report_pdf"
    ]


def run_independent_fetcher(
    output_dir: Path,
    scenario: str,
    industry_codes: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
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
    ]
    for industry_code in industry_codes or []:
        command.extend(["--industry-code", industry_code])
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def validate_multiple_industries_partial_failure(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(
            output_dir,
            scenario="industry-partial-failure",
            industry_codes=["1238", "4567"],
        )
        if result.returncode != 0:
            errors.append(f"多行业部分失败场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        stock_rows = [row for row in rows if row.get("scope_type") == "stock"]
        industry_rows = [row for row in rows if row.get("scope_type") == "industry"]
        if len(stock_rows) != 4:
            errors.append("行业部分失败不得删除成功的个股研报")
        if len(industry_rows) != 2 or {
            row.get("industry_code") for row in industry_rows
        } != {"4567"}:
            errors.append("行业部分失败必须只保留成功的显式行业，不得增加其他行业")
        industry_errors = [
            row
            for row in research_report_errors(output_dir)
            if row.get("code") in {"1238", "4567"}
        ]
        if len(industry_errors) != 1 or (
            industry_errors[0].get("code") != "1238"
            or industry_errors[0].get("stage") != "research_report_index"
        ):
            errors.append("行业索引失败必须按失败行业代码记录 research_report_index")
        downloaded = [
            row
            for row in industry_rows
            if row.get("local_pdf_path") != "来源缺失"
        ]
        if len(downloaded) != 1:
            errors.append("行业 PDF 上限必须按每个显式行业独立应用")

        independent = run_independent_fetcher(
            output_dir,
            "industry-partial-failure",
            ["1238", "4567"],
        )
        if independent.returncode != 0:
            errors.append("部分行业失败且其他对象成功时独立抓取入口必须返回成功")


def validate_shared_report_identity_and_pdf_reuse(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(
            output_dir,
            scenario="shared-report",
            index_limit=1,
            pdf_limit=1,
            industry_codes=["1238"],
        )
        if result.returncode != 0:
            errors.append(f"跨范围共享报告场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        by_report: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            by_report.setdefault(row.get("report_id", ""), []).append(row)
        shared = [group for group in by_report.values() if len(group) > 1]
        if len(shared) != 1 or {row.get("scope_type") for row in shared[0]} != {
            "stock",
            "industry",
        }:
            errors.append("索引身份必须同时保留范围类型、对象标识和稳定报告 ID")
            return
        local_paths = {row.get("local_pdf_path") for row in shared[0]}
        if len(local_paths) != 1 or "来源缺失" in local_paths:
            errors.append("同一稳定报告 ID 的个股/行业索引必须复用同一本地 PDF")
            return
        shared_path = next(iter(local_paths))
        material_files = list((output_dir / "research_reports").glob("*.pdf"))
        if len(material_files) != 2:
            errors.append(f"3 个范围对象含 1 个共享报告时应仅保存 2 份 PDF，实际 {len(material_files)}")

        stock_only = run_independent_fetcher(output_dir, "success")
        if stock_only.returncode != 0:
            errors.append("跨范围复用场景的后续纯个股抓取失败")
            return
        shared_report_id = shared[0][0]["report_id"]
        repeated_shared_rows = [
            row
            for row in read_rows(output_dir / "research_reports.csv")
            if row.get("report_id") == shared_report_id
        ]
        if not repeated_shared_rows or repeated_shared_rows[0].get("local_pdf_path") != shared_path:
            errors.append("后续纯个股抓取必须按稳定报告 ID 复用先前行业范围落盘的 PDF")


def validate_multiple_industries_defaults(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        output_dir.mkdir()
        with (output_dir / "peer_universe.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=["code", "name"])
            writer.writeheader()
            writer.writerow({"code": "300750.SZ", "name": "宁德时代"})
        result = run_independent_fetcher(output_dir, "success", ["1238", "4567"])
        if result.returncode != 0:
            errors.append(f"独立入口多行业默认场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        industry_rows = [row for row in rows if row.get("scope_type") == "industry"]
        counts: dict[str, int] = {}
        downloaded: dict[str, int] = {}
        for row in industry_rows:
            code = row.get("industry_code", "")
            counts[code] = counts.get(code, 0) + 1
            if row.get("local_pdf_path") != "来源缺失":
                downloaded[code] = downloaded.get(code, 0) + 1
        if counts != {"1238": 3, "4567": 3}:
            errors.append(f"多行业默认索引必须按每行业独立保留结果，实际 {counts}")
        if downloaded != {"1238": 3, "4567": 3}:
            errors.append(f"多行业默认必须按每行业下载最新 3 份 PDF，实际 {downloaded}")
        for industry_code in ["1238", "4567"]:
            keys = [
                (row.get("publish_date", ""), row.get("report_id", ""))
                for row in industry_rows
                if row.get("industry_code") == industry_code
            ]
            if keys != sorted(
                keys,
                key=lambda item: (-int(item[0].replace("-", "")), item[1]),
            ):
                errors.append(f"行业 {industry_code} 未按发布日期降序、报告 ID 升序排序")
        manifest = json.loads((output_dir / "source_manifest.json").read_text(encoding="utf-8"))
        entries = {
            item.get("file"): item
            for item in manifest.get("files", [])
            if isinstance(item, dict)
        }
        index_basis = str(entries.get("research_reports.csv", {}).get("period_or_basis", ""))
        material_basis = str(entries.get("research_reports/", {}).get("period_or_basis", ""))
        for token in ["730", "20", "1238", "4567"]:
            if token not in index_basis:
                errors.append(f"多行业默认索引来源口径缺少 `{token}`")
        if "3" not in material_basis:
            errors.append("多行业默认 PDF 来源口径缺少下载上限 3")


def validate_industry_pdf_partial_failure(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(
            output_dir,
            scenario="pdf-partial-failure",
            pdf_limit=2,
            industry_codes=["1238"],
        )
        if result.returncode != 0:
            errors.append(f"行业 PDF 部分失败场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        industry_rows = [
            row
            for row in read_rows(output_dir / "research_reports.csv")
            if row.get("scope_type") == "industry"
        ]
        if len(industry_rows) != 2:
            errors.append("行业 PDF 失败不得删除对应行业索引行")
        if len(
            [row for row in industry_rows if row.get("local_pdf_path") == "来源缺失"]
        ) != 1:
            errors.append("行业 PDF 部分失败应保留一份成功并标记一份来源缺失")
        industry_pdf_errors = [
            row
            for row in research_report_pdf_errors(output_dir)
            if row.get("code") == "1238"
        ]
        if len(industry_pdf_errors) != 1:
            errors.append("行业 PDF 失败必须按行业代码记录 research_report_pdf")


def validate_all_stock_and_industry_requests_fail(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(
            output_dir,
            scenario="all-failure",
            industry_codes=["1238", "4567"],
        )
        if result.returncode != 0:
            errors.append("全部个股与行业索引失败时一键准备必须继续完成")
            return
        if "warning: fetch_a_share_research_reports.py exited 1" not in result.stderr:
            errors.append("全部个股与行业索引失败时一键准备必须输出可选阶段告警")
        report_errors = research_report_errors(output_dir)
        if len(report_errors) != 4 or {row.get("code") for row in report_errors} != {
            "300750.SZ",
            "002594.SZ",
            "1238",
            "4567",
        }:
            errors.append("全部失败时必须按每个股票和显式行业保留索引错误")
        independent = run_independent_fetcher(
            output_dir,
            "all-failure",
            ["1238", "4567"],
        )
        if independent.returncode == 0:
            errors.append("全部个股与显式行业索引请求失败时独立入口必须返回非零")


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


def validate_skip_pdf_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, skip_pdf_download=True)
        if result.returncode != 0:
            errors.append(f"跳过 PDF 场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        if not rows or any(row.get("local_pdf_path") != "来源缺失" for row in rows):
            errors.append("跳过 PDF 时必须保留索引并将本地路径标记为来源缺失")
        material_dir = output_dir / "research_reports"
        if not material_dir.is_dir() or any(material_dir.iterdir()):
            errors.append("跳过 PDF 时必须保留空的稳定研报材料目录")
        if research_report_pdf_errors(output_dir):
            errors.append("跳过 PDF 不应记录 research_report_pdf 下载错误")
        manifest = json.loads((output_dir / "source_manifest.json").read_text(encoding="utf-8"))
        material_entries = [
            item for item in manifest.get("files", []) if item.get("file") == "research_reports/"
        ]
        material_basis = str(material_entries[0].get("period_or_basis", "")) if material_entries else ""
        if "跳过下载=是" not in material_basis:
            errors.append("来源清单必须明确记录 PDF 已跳过")
        auto_manifest = json.loads(
            (output_dir / "auto_prepare_manifest.json").read_text(encoding="utf-8")
        )
        if auto_manifest.get("inputs", {}).get("skip_research_report_pdf_download") is not True:
            errors.append("一键准备清单必须记录 PDF 跳过选项")


def validate_auto_prepare_pdf_defaults(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, pdf_limit=None, index_limit=4)
        if result.returncode != 0:
            errors.append(f"一键准备 PDF 默认值场景退出码为 {result.returncode}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        counts: dict[str, int] = {}
        for row in rows:
            if row.get("local_pdf_path") == "来源缺失":
                continue
            code = row.get("security_code", "")
            counts[code] = counts.get(code, 0) + 1
        if not counts or any(count != 3 for count in counts.values()):
            errors.append(f"一键准备默认必须下载每证券最新 3 份 PDF，实际 {counts}")
        auto_manifest = json.loads(
            (output_dir / "auto_prepare_manifest.json").read_text(encoding="utf-8")
        )
        inputs = auto_manifest.get("inputs", {})
        if inputs.get("research_report_pdf_limit") != 3:
            errors.append("一键准备清单必须记录默认 PDF 上限 3")
        if inputs.get("skip_research_report_pdf_download") is not False:
            errors.append("一键准备清单必须记录默认不跳过 PDF")


def validate_pdf_partial_failure_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(
            output_dir,
            scenario="pdf-partial-failure",
            pdf_limit=2,
        )
        if result.returncode != 0:
            errors.append(f"PDF 部分失败场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        if len(rows) != 4:
            errors.append("单份 PDF 失败不得删除对应索引行")
        succeeded = [row for row in rows if row.get("local_pdf_path") != "来源缺失"]
        failed = [row for row in rows if row.get("local_pdf_path") == "来源缺失"]
        if len(succeeded) != 2 or len(failed) != 2:
            errors.append(f"PDF 部分失败应保留 2 份成功、2 份缺失，实际 {len(succeeded)}/{len(failed)}")
        pdf_errors = research_report_pdf_errors(output_dir)
        if len(pdf_errors) != 2 or any("fixture research report PDF failure" not in row["error"] for row in pdf_errors):
            errors.append("单份 PDF 失败必须写入 research_report_pdf 错误记录")
        if research_report_errors(output_dir):
            errors.append("PDF 失败不得改变索引阶段的成功记录")


def validate_invalid_pdf_scenario(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "research-pack"
        result = run_auto_prepare(output_dir, scenario="pdf-non-pdf", pdf_limit=2)
        if result.returncode != 0:
            errors.append(f"无效 PDF 场景退出码为 {result.returncode}: {result.stderr.strip()}")
            return
        rows = read_rows(output_dir / "research_reports.csv")
        if any(row.get("local_pdf_path") != "来源缺失" for row in rows):
            errors.append("HTML 或过小响应不得写入研报索引的本地路径")
        material_dir = output_dir / "research_reports"
        if not material_dir.is_dir() or any(material_dir.iterdir()):
            errors.append("HTML 或过小响应不得作为有效 PDF 保留")
        pdf_errors = research_report_pdf_errors(output_dir)
        if len(pdf_errors) != 4:
            errors.append(f"4 份无效 PDF 应分别记录错误，实际 {len(pdf_errors)} 条")
        messages = "\n".join(row.get("error", "") for row in pdf_errors)
        for token in ["文件签名", "响应过小"]:
            if token not in messages:
                errors.append(f"无效 PDF 错误必须区分 `{token}`")


def validate_pdf_directory_escape_is_rejected(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peer_path = root / "peer_universe.csv"
        with peer_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["code", "name"])
            writer.writeheader()
            writer.writerow({"code": "300750.SZ", "name": "宁德时代"})
        output_dir = root / "research-pack"
        output_dir.mkdir()
        outside_dir = root / "outside"
        outside_dir.mkdir()
        (output_dir / "research_reports").symlink_to(outside_dir, target_is_directory=True)
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
                "--limit-per-security",
                "1",
                "--pdf-limit-per-security",
                "1",
                "--source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"PDF 目录越界应只降级下载，实际退出码 {result.returncode}")
            return
        if any(outside_dir.iterdir()):
            errors.append("research_reports 目录符号链接导致 PDF 写出研究数据包")
        rows = read_rows(output_dir / "research_reports.csv")
        if not rows or any(row.get("local_pdf_path") != "来源缺失" for row in rows):
            errors.append("PDF 目录越界时索引必须保留且本地路径标记为来源缺失")
        if len(research_report_pdf_errors(output_dir)) != 1:
            errors.append("PDF 目录越界必须记录 research_report_pdf 错误")


def validate_pdf_temporary_symlink_escape_is_rejected(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        output_dir = root / "research-pack"
        output_dir.mkdir()
        peer_path = root / "peer_universe.csv"
        with peer_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["code", "name"])
            writer.writeheader()
            writer.writerow({"code": "300750.SZ", "name": "宁德时代"})
        command = [
            sys.executable,
            str(FETCHER),
            "--peer-universe",
            str(peer_path),
            "--output-dir",
            str(output_dir),
            "--as-of",
            "2026-07-13",
            "--limit-per-security",
            "1",
            "--pdf-limit-per-security",
            "1",
            "--source",
            "fixture",
        ]
        first = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        if first.returncode != 0:
            errors.append("临时文件符号链接场景无法建立初始 PDF")
            return
        row = read_rows(output_dir / "research_reports.csv")[0]
        pdf_path = output_dir / row["local_pdf_path"]
        pdf_path.unlink()
        outside_path = root / "outside.pdf"
        sentinel = b"outside sentinel"
        outside_path.write_bytes(sentinel)
        temporary_path = pdf_path.with_suffix(pdf_path.suffix + ".part")
        temporary_path.symlink_to(outside_path)

        repeated = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        if repeated.returncode != 0:
            errors.append("临时文件符号链接应安全替换为正常 PDF")
            return
        if outside_path.read_bytes() != sentinel:
            errors.append("预置的 .part 符号链接导致 PDF 写出研报材料目录")
        if pdf_path.is_symlink() or not pdf_path.read_bytes().startswith(b"%PDF-"):
            errors.append("临时符号链接处理后必须得到材料目录内的普通 PDF 文件")


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
        "--pdf-limit-per-security",
        "--skip-pdf-download",
        "--industry-code",
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
        default_rows = read_rows(root / "output" / "research_reports.csv")
        if len([row for row in default_rows if row.get("local_pdf_path") != "来源缺失"]) != 3:
            errors.append("独立抓取器默认必须下载每证券最新 3 份 PDF")
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
    validate_single_industry_scenario(errors)
    validate_industry_no_data_scenario(errors)
    validate_multiple_industries_partial_failure(errors)
    validate_shared_report_identity_and_pdf_reuse(errors)
    validate_multiple_industries_defaults(errors)
    validate_industry_pdf_partial_failure(errors)
    validate_no_data_scenario(errors)
    validate_null_data_response_is_no_data(errors)
    validate_partial_failure_scenario(errors)
    validate_skip_pdf_scenario(errors)
    validate_auto_prepare_pdf_defaults(errors)
    validate_pdf_partial_failure_scenario(errors)
    validate_invalid_pdf_scenario(errors)
    validate_pdf_directory_escape_is_rejected(errors)
    validate_pdf_temporary_symlink_escape_is_rejected(errors)
    validate_all_failure_scenario(errors)
    validate_all_stock_and_industry_requests_fail(errors)
    return errors


def main() -> int:
    errors = validate_research_report_fetcher()
    if errors:
        print(f"FAIL - {len(errors)} 个 A 股研报索引与 PDF 问题:", file=sys.stderr)
        for error in errors:
            print(f"  x {error}", file=sys.stderr)
        return 1
    print("OK - A 股研报索引与 PDF 检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
