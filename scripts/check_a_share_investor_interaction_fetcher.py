#!/usr/bin/env python3
"""离线验证 A 股互动平台问答公开 CLI 契约。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FETCHER = ROOT / "scripts/fetch_a_share_investor_interactions.py"
AUTO_PREPARE = ROOT / "scripts/auto_prepare_a_share_research_pack.py"

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


def write_peers(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name"])
        writer.writeheader()
        writer.writerows(
            [
                {"code": "002594.SZ", "name": "比亚迪"},
                {"code": "603119.SH", "name": "浙江荣泰"},
            ]
        )


def write_codes(path: Path, codes: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name"])
        writer.writeheader()
        for index, code in enumerate(codes, start=1):
            writer.writerow({"code": code, "name": f"样本{index}"})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_fetcher(
    root: Path,
    scenario: str,
    *,
    codes: list[str] | None = None,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    peers = root / "peers.csv"
    if codes is None:
        write_peers(peers)
    else:
        write_codes(peers, codes)
    return subprocess.run(
        [
            sys.executable,
            str(FETCHER),
            "--peer-universe",
            str(peers),
            "--output-dir",
            str(root / "output"),
            "--as-of",
            "2026-08-13",
            "--source",
            "fixture",
            "--fixture-scenario",
            scenario,
            *(extra or []),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def validate_success(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        output = root / "output"
        write_peers(peers)
        result = subprocess.run(
            [
                sys.executable,
                str(FETCHER),
                "--peer-universe",
                str(peers),
                "--output-dir",
                str(output),
                "--as-of",
                "2026-08-13",
                "--source",
                "fixture",
                "--fixture-scenario",
                "success",
                "--lookback-days",
                "30",
                "--limit-per-security",
                "1",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"成功场景退出码为 {result.returncode}: {result.stderr}")
            return
        path = output / "investor_interactions.csv"
        if not path.is_file():
            errors.append("成功场景缺少 investor_interactions.csv")
            return
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != INTERACTION_COLUMNS:
                errors.append(f"互动问答列不符合契约: {reader.fieldnames}")
            rows = list(reader)
        if {row.get("platform") for row in rows} != {"深交所互动易", "上证e互动"}:
            errors.append("成功场景必须同时覆盖深交所互动易和上证e互动")
        if len(rows) != 2:
            errors.append(f"每证券上限为 1 时应输出 2 条问答，实际 {len(rows)} 条")
        if any(
            row["question_time"] > "2026-08-13 23:59:59"
            or row["answer_time"] > "2026-08-13 23:59:59"
            or row["answer_time"] < "2026-07-14 00:00:00"
            for row in rows
        ):
            errors.append("互动问答未遵守研究截止日或回溯窗口")
        if any(
            row["platform"] == "深交所互动易"
            and row["question_time"] >= "2026-07-14 00:00:00"
            for row in rows
        ):
            errors.append("fixture 必须覆盖窗口前提问、窗口内回答，防止按问题时间误筛")
        expected_order = sorted(
            rows,
            key=lambda row: (
                row["security_code"],
                tuple(-ord(char) for char in row["answer_time"]),
                row["source_record_id"],
            ),
        )
        if rows != expected_order:
            errors.append("互动问答未按证券代码、回答时间降序、来源记录 ID 稳定排序")
        if any(
            not row["interaction_id"].startswith("iq_")
            or len(row["interaction_id"]) != 27
            or row["source_type"] != "company_public_material"
            or row["verification_status"] != "待验证"
            or "问题断言不构成事实" not in row["basis"]
            or "公告" not in row["basis"]
            for row in rows
        ):
            errors.append("互动问答缺少稳定 ID 或公司公开材料证据边界")
        rows_by_platform = {row["platform"]: row for row in rows}
        sz_row = rows_by_platform.get("深交所互动易", {})
        if (
            sz_row.get("source_record_id") != "2334000000000000001"
            or sz_row.get("question_source") != "APP"
            or "questionId=2334000000000000001" not in sz_row.get("source_url", "")
        ):
            errors.append("深交所互动易 JSON 字段未按公开响应映射")
        sh_row = rows_by_platform.get("上证e互动", {})
        if (
            sh_row.get("source_record_id") != "1778445"
            or sh_row.get("question_source") != "Android"
            or sh_row.get("answerer") != "浙江荣泰"
            or "uid=275524#item-1778445" not in sh_row.get("source_url", "")
        ):
            errors.append("上证e互动 HTML 字段未按公开响应映射")

        manifest_path = output / "source_manifest.json"
        errors_path = output / "fetch_errors.csv"
        if not manifest_path.is_file() or not errors_path.is_file():
            errors.append("成功场景缺少 source_manifest.json 或 fetch_errors.csv")
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = [
            item
            for item in manifest.get("files", [])
            if item.get("file") == "investor_interactions.csv"
        ]
        if len(entries) != 1 or any(
            token not in str(entries[0])
            for token in ("30", "1", "互动易", "上证e互动", "公告", "问题")
        ):
            errors.append("互动问答来源清单缺少默认窗口、上限、平台或证据边界")
        with errors_path.open(newline="", encoding="utf-8") as handle:
            if list(csv.DictReader(handle)):
                errors.append("成功场景不应写入抓取错误")


def validate_failure_semantics(errors: list[str]) -> None:
    expectations = {
        "no-data": (0, 0, "investor_interaction_no_data", 2),
        "future-only": (0, 0, "investor_interaction_no_data", 2),
        "partial-failure": (0, 1, "investor_interaction", 1),
        "all-failure": (1, 0, "investor_interaction", 2),
    }
    for scenario, (returncode, minimum_rows, stage, stage_count) in expectations.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_fetcher(root, scenario)
            if result.returncode != returncode:
                errors.append(
                    f"{scenario} 退出码为 {result.returncode}，预期 {returncode}"
                )
                continue
            output = root / "output"
            for filename in (
                "investor_interactions.csv",
                "source_manifest.json",
                "fetch_errors.csv",
            ):
                if not (output / filename).is_file():
                    errors.append(f"{scenario} 缺少稳定输出 {filename}")
            rows = read_rows(output / "investor_interactions.csv")
            if len(rows) < minimum_rows:
                errors.append(f"{scenario} 未保留可用互动问答")
            if scenario in {"no-data", "future-only", "all-failure"} and rows:
                errors.append(f"{scenario} 应输出空的稳定问答表")
            notices = read_rows(output / "fetch_errors.csv")
            matching = [row for row in notices if row.get("stage") == stage]
            if len(matching) != stage_count:
                errors.append(
                    f"{scenario} 的 {stage} 记录数为 {len(matching)}，预期 {stage_count}"
                )
            if scenario == "no-data" and any(
                row.get("stage") == "investor_interaction" for row in notices
            ):
                errors.append("真实无数据不得混记为来源失败")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(root, "duplicate")
        if result.returncode != 0:
            errors.append(f"重复记录场景退出失败: {result.stderr}")
        else:
            rows = read_rows(root / "output" / "investor_interactions.csv")
            if len(rows) != 2 or len({row["interaction_id"] for row in rows}) != 2:
                errors.append("跨页重复互动问答未按稳定 ID 去重")

    malformed_expectations = {
        "malformed-cninfo-detail": ["002594.SZ"],
        "malformed-sse-html": ["603119.SH"],
        "malformed-sse-uid": ["603119.SH"],
    }
    for scenario, codes in malformed_expectations.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_fetcher(root, scenario, codes=codes)
            if result.returncode != 1:
                errors.append(f"{scenario} 必须按来源失败返回非零")
                continue
            notices = read_rows(root / "output" / "fetch_errors.csv")
            if not any(row.get("stage") == "investor_interaction" for row in notices):
                errors.append(f"{scenario} 缺少 investor_interaction 解析失败")
            if any(
                row.get("stage") == "investor_interaction_no_data"
                for row in notices
            ):
                errors.append(f"{scenario} 不得误记为真实无数据")


def validate_tie_limit(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(
            root,
            "tie-limit",
            codes=["002594.SZ"],
            extra=["--limit-per-security", "1"],
        )
        if result.returncode != 0:
            errors.append(f"同秒回答限额场景失败: {result.stderr}")
            return
        rows = read_rows(root / "output" / "investor_interactions.csv")
        if len(rows) != 1 or rows[0].get("source_record_id") != "100":
            errors.append("同秒回答达到限额时必须优先保留来源记录 ID 较小者")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = run_fetcher(
            root,
            "cninfo-page-duplicate",
            codes=["002594.SZ"],
            extra=["--limit-per-security", "2"],
        )
        if result.returncode != 0:
            errors.append(f"互动易跨页重复场景失败: {result.stderr}")
            return
        rows = read_rows(root / "output" / "investor_interactions.csv")
        if len(rows) != 2 or {row["source_record_id"] for row in rows} != {"100", "200"}:
            errors.append("互动易候选必须在执行每证券限额前按问题 ID 去重")


def validate_inputs_and_stability(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        output = root / "output"
        output.mkdir()
        write_codes(
            peers,
            ["2594", "002594.SZ", "603119", "430047.BJ", "200001.SZ"],
        )
        (output / "source_manifest.json").write_text(
            '{"files":[{"file":"keep.csv"}]}\n',
            encoding="utf-8",
        )
        (output / "fetch_errors.csv").write_text(
            "code,source,stage,error\nkeep,keep,keep,keep\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            str(FETCHER),
            "--peer-universe",
            str(peers),
            "--output-dir",
            str(output),
            "--as-of",
            "2026-08-13",
            "--source",
            "fixture",
        ]
        first = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        first_content = (output / "investor_interactions.csv").read_text(encoding="utf-8")
        second = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        second_content = (output / "investor_interactions.csv").read_text(encoding="utf-8")
        if first.returncode != 0 or second.returncode != 0:
            errors.append(f"混合股票池应保留有效证券: {first.stderr}{second.stderr}")
            return
        rows = read_rows(output / "investor_interactions.csv")
        if {row["security_code"] for row in rows} != {"002594.SZ", "603119.SH"}:
            errors.append("股票代码未规范化、去重或隔离非沪深 A 股")
        if len({row["interaction_id"] for row in rows}) != len(rows):
            errors.append("重复输入产生了重复互动问答")
        if first_content != second_content:
            errors.append("相同输入重复运行产生了问答顺序或内容漂移")
        notices = read_rows(output / "fetch_errors.csv")
        if not any(row.get("stage") == "keep" for row in notices):
            errors.append("互动问答抓取覆盖了无关错误记录")
        if not any(
            row.get("code") == "200001.SZ"
            and row.get("stage") == "investor_interaction_input"
            for row in notices
        ):
            errors.append("深市 B 股输入未记录为 investor_interaction_input")
        if not any(
            row.get("code") == "430047.BJ"
            and row.get("stage") == "investor_interaction_unsupported"
            for row in notices
        ):
            errors.append("北交所输入未显式记录为当前不支持")
        manifest = json.loads((output / "source_manifest.json").read_text(encoding="utf-8"))
        files = manifest.get("files", [])
        if not any(item.get("file") == "keep.csv" for item in files):
            errors.append("互动问答抓取覆盖了无关来源清单")
        if sum(item.get("file") == "investor_interactions.csv" for item in files) != 1:
            errors.append("重复运行产生了重复互动问答来源清单")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peers = root / "peers.csv"
        output = root / "output"
        write_codes(peers, ["bad", "200001.SZ"])
        result = subprocess.run(
            [
                sys.executable,
                str(FETCHER),
                "--peer-universe",
                str(peers),
                "--output-dir",
                str(output),
                "--as-of",
                "2026-08-13",
                "--source",
                "fixture",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 1:
            errors.append("全部输入无效时独立抓取器必须返回非零")
        for filename in (
            "investor_interactions.csv",
            "source_manifest.json",
            "fetch_errors.csv",
        ):
            if not (output / filename).is_file():
                errors.append(f"全部输入无效时缺少稳定输出 {filename}")


def auto_prepare_command(output: Path) -> list[str]:
    return [
        sys.executable,
        str(AUTO_PREPARE),
        "--theme",
        "互动平台 fixture",
        "--output-dir",
        str(output),
        "--as-of",
        "2026-08-13",
        "--universe-source",
        "fixture",
        "--market-source",
        "fixture",
        "--financial-source",
        "fixture",
        "--research-report-source",
        "fixture",
        "--market-activity-source",
        "fixture",
        "--investor-interaction-source",
        "fixture",
    ]


def validate_auto_prepare(errors: list[str]) -> None:
    help_result = subprocess.run(
        [sys.executable, str(AUTO_PREPARE), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    for flag in (
        "--investor-interaction-source",
        "--investor-interaction-fixture-scenario",
        "--investor-interaction-lookback-days",
        "--investor-interaction-limit-per-security",
        "--skip-investor-interactions",
    ):
        if flag not in help_result.stdout:
            errors.append(f"一键入口帮助缺少 {flag}")

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "pack"
        result = subprocess.run(
            [
                *auto_prepare_command(output),
                "--investor-interaction-fixture-scenario",
                "all-failure",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"互动问答可选阶段失败不应阻断核心包: {result.stderr}")
        elif "warning: fetch_a_share_investor_interactions.py exited 1" not in result.stderr:
            errors.append("一键入口未显式提示互动问答来源完全失败")
        if not (output / "investor_interactions.csv").is_file():
            errors.append("一键入口缺少稳定 investor_interactions.csv")
        auto_manifest_path = output / "auto_prepare_manifest.json"
        if auto_manifest_path.is_file():
            manifest = json.loads(auto_manifest_path.read_text(encoding="utf-8"))
            inputs = manifest.get("inputs", {})
            for key in (
                "investor_interaction_source",
                "investor_interaction_fixture_scenario",
                "investor_interaction_lookback_days",
                "investor_interaction_limit_per_security",
                "skip_investor_interactions",
            ):
                if key not in inputs:
                    errors.append(f"一键准备清单缺少 {key}")
        else:
            errors.append("一键入口失败后缺少 auto_prepare_manifest.json")

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "pack"
        initial = subprocess.run(
            auto_prepare_command(output),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        skipped = subprocess.run(
            [*auto_prepare_command(output), "--force", "--skip-investor-interactions"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if initial.returncode != 0 or skipped.returncode != 0:
            errors.append(f"互动问答强制重跑跳过失败: {initial.stderr}{skipped.stderr}")
            return
        if (output / "investor_interactions.csv").exists():
            errors.append("强制重跑跳过互动问答时未清除旧 CSV")
        source_manifest = json.loads(
            (output / "source_manifest.json").read_text(encoding="utf-8")
        )
        if any(
            item.get("file") == "investor_interactions.csv"
            for item in source_manifest.get("files", [])
        ):
            errors.append("强制重跑跳过互动问答时未清除旧来源清单")
        notices = read_rows(output / "fetch_errors.csv")
        if any(
            row.get("stage", "").startswith("investor_interaction")
            for row in notices
        ):
            errors.append("强制重跑跳过互动问答时未清除旧错误记录")


def validate_investor_interaction_fetcher() -> list[str]:
    errors: list[str] = []
    if not FETCHER.is_file():
        errors.append(f"缺少抓取器: {FETCHER.relative_to(ROOT)}")
        return errors
    validate_success(errors)
    validate_failure_semantics(errors)
    validate_tie_limit(errors)
    validate_inputs_and_stability(errors)
    validate_auto_prepare(errors)
    return errors


def main() -> int:
    errors = validate_investor_interaction_fetcher()
    if errors:
        print(f"FAIL - {len(errors)} 个互动平台问答问题:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("OK - A 股互动平台问答检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
