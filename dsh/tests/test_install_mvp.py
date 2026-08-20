#!/usr/bin/env python3
"""Seam 2 — install-validity test for the DSH MVP preset installer.

CI-automatable: needs bash, python3 + PyYAML, and a checkout of this repo.
No DEEPSEEK_API_KEY, no model call, no web UI: the test runs
`bash dsh/install-mvp.sh` against an isolated $HOME and verifies the
installed preset contract from the spec (`.scratch/dsh-mvp/spec-dsh-mvp.md`):

  (a) ~/.dsh/.agent-presets/<id>/agent.cordis.yml exists and parses as YAML
      (the DSH runtime's `!!js` expressions are stripped before the parse —
      evaluating them is DSH's job, not this test's);
  (b) the persona text is non-empty and byte-identical to the body of
      plugins/agent-plugins/<id>/agents/<id>.md after its frontmatter
      (a single leading blank line is dropped — see dsh/persona.py);
  (c) customSkillDirs points at the researcher skills root and all six
      SKILL.md are present there;
  (d) the expected rows are mounted and the delegation group is absent;
  (e) re-running the installer is idempotent (byte-identical output).

Run from anywhere; the repo root is resolved from this file:
    .venv/bin/python dsh/tests/test_install_mvp.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESET_ID = "a-share-market-researcher"
AGENT_MD = ROOT / "plugins" / "agent-plugins" / PRESET_ID / "agents" / f"{PRESET_ID}.md"
INSTALL_SH = ROOT / "dsh" / "install-mvp.sh"
SKILLS_DIR = ROOT / "plugins" / "agent-plugins" / PRESET_ID / "skills"
SRC_TEMPLATE = ROOT / "dsh" / "presets" / PRESET_ID / "agent.cordis.yml"

EXPECTED_SKILLS = {
    "a-share-competitive-analysis",
    "a-share-comps-analysis",
    "a-share-data-sources",
    "a-share-idea-generation",
    "a-share-sector-overview",
    "pptx-author",
}

# Rows the MVP preset must mount (spec Implementation Decisions).
EXPECTED_ROWS = {
    "persona",
    "agent-instructions",
    "tool-bash",
    "tool-pwsh",
    "tool-fs",
    "tool-fs-search",
    "tool-jobs",
    "skill-filesystem",
    "tool-skill",
    "tool-goal",
    "planning",
    "compaction",
    "tool-ask-user",
    "tool-todo",
    "tool-web",
}

# The delegation group is explicitly out of scope for the MVP.
FORBIDDEN_ROWS = {
    "delegation",
    "tool-subagent",
    "tool-subagent-fork",
    "tool-subagent-control",
    "tool-subagent-list-agents",
    "workflow-worker-thread",
    "tool-workflow",
    "tool-ralph",
}

try:
    import yaml
except ImportError:  # pragma: no cover - environment check
    print("错误：需要 PyYAML。请用 .venv/bin/python 运行本测试（或 pip install pyyaml）。", file=sys.stderr)
    sys.exit(2)

try:
    sys.path.insert(0, str(ROOT / "dsh"))
    from persona import persona_body  # noqa: E402
except ImportError:  # pragma: no cover - red-phase guard
    print(f"错误：缺少 {ROOT / 'dsh' / 'persona.py'}（persona 正文提取逻辑）。", file=sys.stderr)
    sys.exit(1)


def strip_js_tags(text: str) -> str:
    """Remove DSH `!!js` tag prefixes so yaml.safe_load can check structure.

    The `!!js` expressions (platform gates, customSkillDirs) are evaluated by
    DSH's own preset loader at runtime; this test only verifies the YAML
    structure around them.
    """
    return re.sub(r"!!js\s+", "", text)


def load_rows(agent_cordis: Path):
    rows = yaml.safe_load(strip_js_tags(agent_cordis.read_text(encoding="utf-8")))
    if not isinstance(rows, list):
        raise AssertionError("agent.cordis.yml 顶层必须是行列表（list of rows）")
    by_id = {row["id"]: row for row in rows if isinstance(row, dict) and "id" in row}
    return rows, by_id


def run_install(home: Path, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOME"] = str(home)  # isolate: the installer writes to $HOME/.dsh/.agent-presets
    env["DEEPSEEK_API_KEY"] = "ci-dummy-key-presence-check-only"
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


def main() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # ── preconditions ──────────────────────────────────────────────────────
    check(INSTALL_SH.is_file(), f"缺少安装脚本 {INSTALL_SH.relative_to(ROOT)}")
    check(AGENT_MD.is_file(), f"缺少 persona 源 {AGENT_MD.relative_to(ROOT)}")
    check(SKILLS_DIR.is_dir(), f"缺少 skills 目录 {SKILLS_DIR.relative_to(ROOT)}")
    if failures:
        for msg in failures:
            print("FAIL:", msg)
        return 1

    expected_persona = persona_body(AGENT_MD.read_text(encoding="utf-8"))
    check(bool(expected_persona), "persona 正文为空")
    # Independent known-good anchors (not recomputed by the code under test).
    check(
        expected_persona.startswith("你是 A-share Market Researcher"),
        "persona 正文开头与 agents/*.md 不符",
    )
    # Spec Further Notes: persona 正文 65 行 / ~5.6KB (independent literal).
    check(
        len(expected_persona.splitlines()) == 65,
        f"persona 正文应为 65 行（spec），实际 {len(expected_persona.splitlines())}",
    )
    check(
        expected_persona.rstrip().endswith("`pptx-author`"),
        "persona 正文结尾与 agents/*.md 不符",
    )

    # ── install, twice, into an isolated HOME ──────────────────────────────
    with tempfile.TemporaryDirectory(prefix="dsh-mvp-test-") as tmp:
        home = Path(tmp)
        proc1 = run_install(home, ROOT)
        check(proc1.returncode == 0, f"install 第 1 次退出码 {proc1.returncode}：{proc1.stderr.strip()[-400:]}")
        dest = home / ".dsh" / ".agent-presets" / PRESET_ID
        agent_cordis = dest / "agent.cordis.yml"
        preset_yml = dest / "preset.yml"
        check(agent_cordis.is_file(), f"未生成 {agent_cordis}")
        check(preset_yml.is_file(), f"未生成 {preset_yml}")
        bytes_after_first = agent_cordis.read_bytes() if agent_cordis.is_file() else b""

        proc2 = run_install(home, ROOT)
        check(proc2.returncode == 0, f"install 第 2 次退出码 {proc2.returncode}：{proc2.stderr.strip()[-400:]}")
        check(
            agent_cordis.is_file() and agent_cordis.read_bytes() == bytes_after_first,
            "重复安装后 agent.cordis.yml 字节不一致（应幂等）",
        )

        # 缺凭据时 install 应明确失败且不改动已装内容（user story 10）
        env_nokey = dict(os.environ)
        env_nokey["HOME"] = str(home)
        env_nokey.pop("DEEPSEEK_API_KEY", None)
        proc3 = subprocess.run(
            ["bash", str(INSTALL_SH)], cwd=str(ROOT), env=env_nokey, capture_output=True, text=True
        )
        check(proc3.returncode != 0, "缺 DEEPSEEK_API_KEY / credentials.yaml 时 install 应报错退出")
        check("DEEPSEEK_API_KEY" in proc3.stderr, "缺凭据报错应提及 DEEPSEEK_API_KEY")
        check(agent_cordis.is_file() and agent_cordis.read_bytes() == bytes_after_first, "缺凭据失败不应改动已安装内容")

        # ── (a) YAML 可解析 ────────────────────────────────────────────────
        try:
            _, by_id = load_rows(agent_cordis)
        except Exception as exc:  # noqa: BLE001 - report and continue
            check(False, f"agent.cordis.yml YAML 解析失败：{exc}")
            by_id = {}

        # ── (b) persona 逐字节一致 ─────────────────────────────────────────
        persona_row = by_id.get("persona")
        check(persona_row is not None, "缺少 persona 行")
        if persona_row is not None:
            persona_text = (persona_row.get("config") or {}).get("text")
            check(isinstance(persona_text, str) and persona_text, "persona text 为空")
            check(persona_text == expected_persona, "persona text 与 agents/*.md 正文逐字节不一致")

        # ── (c) skills ─────────────────────────────────────────────────────
        sf_row = by_id.get("skill-filesystem")
        check(sf_row is not None, "缺少 skill-filesystem 行")
        if sf_row is not None:
            cfg = sf_row.get("config") or {}
            check(cfg.get("includeDefaultRoots") is False, "skill-filesystem 应 includeDefaultRoots: false")
            dirs = cfg.get("customSkillDirs") or []
            check(len(dirs) == 1, "skill-filesystem 应只有一条 customSkillDirs")
            if dirs:
                expr = str(dirs[0])
                check(expr.startswith("process.cwd()"), f"customSkillDirs 应为 process.cwd() 表达式：{expr!r}")
                check(
                    f"plugins/agent-plugins/{PRESET_ID}/skills" in expr,
                    f"customSkillDirs 未指向 researcher skills 目录：{expr!r}",
                )
        present = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
        check(present == EXPECTED_SKILLS, f"skills 目录应恰好含 6 个 SKILL.md，实际：{sorted(present)}")

        # ── (d) 行集合 ─────────────────────────────────────────────────────
        row_ids = set(by_id)
        check(EXPECTED_ROWS <= row_ids, f"缺少预期行：{sorted(EXPECTED_ROWS - row_ids)}")
        check(not (FORBIDDEN_ROWS & row_ids), f"不应出现 delegation 相关行：{sorted(FORBIDDEN_ROWS & row_ids)}")

        # ── preset 元数据 ──────────────────────────────────────────────────
        meta = yaml.safe_load(preset_yml.read_text(encoding="utf-8"))
        check(isinstance(meta, dict) and meta.get("name") == "A股行业研究", "preset.yml 的 name 应为 A股行业研究")
        check(meta.get("order") == 10, "preset.yml 的 order 应为 10")

        # ── 源文件不被 install 改动 ────────────────────────────────────────
        check(
            "__PERSONA_TEXT__" in SRC_TEMPLATE.read_text(encoding="utf-8"),
            "源模板应保留 __PERSONA_TEXT__ 占位符（install 不得改写仓库源文件）",
        )

    if failures:
        for msg in failures:
            print("FAIL:", msg)
        return 1
    print(f"PASS: dsh/install-mvp.sh 安装有效性（Seam 2）— {len(EXPECTED_SKILLS)} skills / {len(EXPECTED_ROWS)} rows / 幂等")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
