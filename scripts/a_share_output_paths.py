#!/usr/bin/env python3
"""Shared output path conventions for A-share research artifacts."""

from __future__ import annotations

from pathlib import Path


def topic_name(theme: str) -> str:
    cleaned = theme.strip()
    return cleaned or "A股主题"


def topic_dir(theme: str) -> Path:
    return Path("out") / topic_name(theme)


def stage_dir(theme: str, stage: str) -> Path:
    return topic_dir(theme) / stage


def workbook_path(theme: str) -> Path:
    return stage_dir(theme, "workbook") / f"{topic_name(theme)}可比公司.xlsx"
