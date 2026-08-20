#!/usr/bin/env bash
#
# 安装 a-share-market-researcher 的 DSH preset（web profile 用）。
#
# 幂等：每次重跑都会先清空目标目录，再重新拷贝 preset 源并注入 persona，
# 改完 dsh/presets/ 下的源文件后重跑即可更新。
#
# 用法（在仓库根目录运行）：
#   bash dsh/install-mvp.sh
#
# 前置条件：DEEPSEEK_API_KEY 或 ~/.dsh/.credentials.yaml（本脚本只检查存在性，
# dsh 运行时才真正校验凭据）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRESET_ID="a-share-market-researcher"
PRESET_SRC="$ROOT/dsh/presets/$PRESET_ID"
AGENT_MD="$ROOT/plugins/agent-plugins/$PRESET_ID/agents/$PRESET_ID.md"
HOME_DIR="${HOME:-$(printf '%s' ~)}"
DEST="${HOME_DIR}/.dsh/.agent-presets/$PRESET_ID"

# ── 前置检查 ────────────────────────────────────────────────────────────────
# DSH 读取 DeepSeek 凭据的两个位置：环境变量 DEEPSEEK_API_KEY，或
# ~/.dsh/.credentials.yaml（dsh 运行时读取）。两者都没有才报错。
if [[ -z "${DEEPSEEK_API_KEY:-}" && ! -f "$HOME_DIR/.dsh/.credentials.yaml" ]]; then
  echo "错误：未找到 DeepSeek API 凭据：请 export DEEPSEEK_API_KEY=sk-... 或写入 ~/.dsh/.credentials.yaml" >&2
  exit 1
fi

if [[ ! -d "$ROOT/plugins" ]]; then
  echo "错误：没找到 $ROOT/plugins —— 请在仓库根目录运行：bash dsh/install-mvp.sh" >&2
  exit 1
fi

if [[ ! -f "$AGENT_MD" ]]; then
  echo "错误：找不到 persona 源 $AGENT_MD" >&2
  exit 1
fi

if [[ ! -d "$PRESET_SRC" ]]; then
  echo "错误：找不到 preset 源 $PRESET_SRC" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误：需要 python3（用于注入 persona 文本）" >&2
  exit 1
fi

# 以下只是提示，不阻断安装（端到端跑研究前需要）
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "提示：未找到 .venv —— 跑研究前请先创建：python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
fi
if ! command -v dsh >/dev/null 2>&1; then
  echo "提示：未找到 dsh 命令 —— 请先全局安装：npm install -g @deepseek-ai/dsh" >&2
fi

# ── 拷贝 preset 源 + 注入 persona（幂等）────────────────────────────────────
mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -r "$PRESET_SRC" "$DEST"

python3 "$ROOT/dsh/persona.py" render \
  --template "$DEST/agent.cordis.yml" \
  --agent-md "$AGENT_MD" \
  --out "$DEST/agent.cordis.yml"

echo "已安装 preset：$DEST"
echo "启动：cd \"$ROOT\" && dsh --profile web"
