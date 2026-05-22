#!/usr/bin/env python3
"""Prepare a local A-share research-pack from local exports."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

REQUIRED_INPUTS = ["peer_universe.csv"]
OPTIONAL_INPUTS = [
    "market_snapshot.csv",
    "financial_summary.csv",
    "tencent_quotes.csv",
    "akshare_financial_summary.csv",
    "company_exposure.md",
    "events_and_risks.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="Directory containing local raw exports.")
    parser.add_argument("--output-dir", required=True, help="Directory where research-pack files are written.")
    parser.add_argument("--theme", required=True, help="Chinese theme name used in source notes.")
    parser.add_argument("--as-of", required=True, help="Access date or quote timestamp for generated source notes.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_source_manifest(input_dir: Path, theme: str, as_of: str) -> list[dict[str, str]]:
    manifest_path = input_dir / "source_manifest.json"
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = data.get("files")
        if isinstance(files, list):
            return [item for item in files if isinstance(item, dict)]

    return [
        {
            "file": "peer_universe.csv",
            "source_type": "user_provided",
            "source_name": f"{theme} 本地股票池",
            "data_time": as_of,
            "period_or_basis": "用户提供",
            "verification_status": "user_provided",
            "missing_behavior": "缺少股票池时停止 comps 和 idea shortlist",
        }
    ]


def write_source_manifest(output_dir: Path, files: list[dict[str, str]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"files": files}
    (output_dir / "source_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_required_inputs(input_dir: Path, output_dir: Path) -> None:
    for filename in REQUIRED_INPUTS:
        src = input_dir / filename
        if not src.is_file():
            raise FileNotFoundError(f"missing required input: {src}")
        shutil.copyfile(src, output_dir / filename)


def copy_optional_inputs(input_dir: Path, output_dir: Path) -> list[str]:
    copied: list[str] = []
    mapping = {
        "market_snapshot.csv": "market_snapshot.csv",
        "financial_summary.csv": "financial_summary.csv",
        "tencent_quotes.csv": "market_snapshot.csv",
        "akshare_financial_summary.csv": "financial_summary.csv",
        "company_exposure.md": "company_exposure.md",
        "events_and_risks.md": "events_and_risks.md",
    }
    for source_name, target_name in mapping.items():
        src = input_dir / source_name
        if src.is_file():
            target = output_dir / target_name
            if target.is_file():
                continue
            shutil.copyfile(src, target)
            copied.append(target_name)
    return copied


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_files = load_source_manifest(input_dir, args.theme, args.as_of)
    copy_required_inputs(input_dir, output_dir)
    copied = copy_optional_inputs(input_dir, output_dir)

    existing = {item.get("file") for item in manifest_files}
    for filename in copied:
        if filename not in existing:
            manifest_files.append(
                {
                    "file": filename,
                    "source_type": "user_provided",
                    "source_name": f"{args.theme} 本地导出",
                    "data_time": args.as_of,
                    "period_or_basis": "用户提供",
                    "verification_status": "user_provided",
                    "missing_behavior": "缺失时按 a-share-data-sources 降级",
                }
            )

    write_source_manifest(output_dir, manifest_files)
    print(f"wrote research-pack: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
