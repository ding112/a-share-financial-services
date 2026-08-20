#!/usr/bin/env bash
#
# 安装所有 FSI agent 的 DSH preset（web profile 用）。
#
# 通用版 install 脚本：把 dsh/presets/ 下每个 agent preset 拷到
# ~/.dsh/.agent-presets/<slug>/，并用 dsh/persona.py 把对应该 agent 的
# plugins/agent-plugins/<slug>/agents/<slug>.md 正文（去掉 frontmatter）注入
# agent.cordis.yml 的 __PERSONA_TEXT__ 占位符。
#
# 用法（在仓库根运行）：
#   bash dsh/install-presets.sh            # 安装全部 preset（默认）
#   bash dsh/install-presets.sh <slug>     # 只安装某一个（如 a-share-screener）
#
# 幂等：每次重跑都会先清空目标目录，再重新拷贝 preset 源并注入 persona，
# 改完 dsh/presets/ 下的源文件后重跑即可更新。
#
# 前置条件：DEEPSEEK_API_KEY（本脚本只检查存在性，dsh 运行时才真正校验）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_ROOT="${HOME}/.dsh/.agent-presets"

# 要安装的 preset slug 列表：默认取 dsh/presets/ 下所有子目录（排序列，保证幂等），
# 用户也可指定单个 slug。用纯 bash glob，兼容 macOS 自带 bash 3.2（无 mapfile）。
ALL_PRESETS=()
for _d in "$ROOT"/dsh/presets/*/; do
  [[ -d "$_d" ]] || continue
  ALL_PRESETS+=("$(basename "$_d")")
done
# 稳定的安装顺序（按 slug 字典序）
SLUGS=()
while IFS= read -r _s; do
  SLUGS+=("$_s")
done < <(printf '%s\n' "${ALL_PRESETS[@]}" | sort)

if [[ $# -ge 1 && "$1" != "all" ]]; then
  SLUGS=("$1")
fi

# ── 前置检查（凭据校验必须先于任何 rm，保证缺凭据时不改动已装内容）────────────
# DSH 读取 DeepSeek 凭据的两个位置：环境变量 DEEPSEEK_API_KEY，或
# ~/.dsh/.credentials.yaml（dsh 运行时读取）。两者都没有才报错。
if [[ -z "${DEEPSEEK_API_KEY:-}" && ! -f "${HOME}/.dsh/.credentials.yaml" ]]; then
  echo "错误：未找到 DeepSeek API 凭据：请 export DEEPSEEK_API_KEY=sk-... 或写入 ~/.dsh/.credentials.yaml" >&2
  exit 1
fi

if [[ ! -d "$ROOT/plugins" ]]; then
  echo "错误：没找到 $ROOT/plugins —— 请在仓库根目录运行：bash dsh/install-presets.sh" >&2
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

# ── 逐个安装（幂等）：清空目标 → 拷贝 preset 源 → 注入 persona ────────────────
mkdir -p "$DEST_ROOT"

for slug in "${SLUGS[@]}"; do
  PRESET_SRC="$ROOT/dsh/presets/$slug"
  AGENT_MD="$ROOT/plugins/agent-plugins/$slug/agents/$slug.md"

  if [[ ! -d "$PRESET_SRC" ]]; then
    echo "错误：缺少 preset 源 $PRESET_SRC" >&2
    exit 1
  fi
  if [[ ! -f "$AGENT_MD" ]]; then
    echo "错误：缺少 persona 源 $AGENT_MD" >&2
    exit 1
  fi

  DEST="$DEST_ROOT/$slug"
  rm -rf "$DEST"
  cp -r "$PRESET_SRC" "$DEST"

  python3 "$ROOT/dsh/persona.py" render \
    --template "$DEST/agent.cordis.yml" \
    --agent-md "$AGENT_MD" \
    --out "$DEST/agent.cordis.yml"

  echo "已安装 preset：$slug → $DEST"
done

echo "完成，共安装 ${#SLUGS[@]} 个 preset：${SLUGS[*]}"
echo "启动：cd \"$ROOT\" && dsh --profile web"
