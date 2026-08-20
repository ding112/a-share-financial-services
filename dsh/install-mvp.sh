#!/usr/bin/env bash
#
# 向后兼容的安装入口：等价于 `bash dsh/install-presets.sh a-share-market-researcher`。
#
# 新代码请直接用 dsh/install-presets.sh：它支持安装全部 FSI agent preset（默认）
# 或单个（bash dsh/install-presets.sh <slug>）。本脚本保留只为不破坏既有调用方。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$DIR/install-presets.sh" a-share-market-researcher
