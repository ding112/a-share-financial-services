#!/usr/bin/env python3
"""Install-validity test for the generalized DSH preset installer (all 6 agents).

Extends dsh/tests/test_install_mvp.py (which pins the single a-share wrapper) to
cover every FSI agent preset: runs `bash dsh/install-presets.sh all` against an
isolated $HOME and asserts, per agent:

  (a) ~/.dsh/.agent-presets/<slug>/agent.cordis.yml exists and parses as YAML
      (the DSH runtime's `!!js` expressions are stripped before the parse);
  (b) the persona text is byte-identical to the body of
      plugins/agent-plugins/<slug>/agents/<slug>.md after its frontmatter
      (see dsh/persona.py);
  (c) customSkillDirs points at the agent's bundled skills root and contains
      exactly the expected SKILL.md names;
  (d) the expected rows are mounted and the delegation group is absent;
  (e) preset.yml metadata (name / order) is correct;
  (f) re-running the installer is idempotent (byte-identical output) and a
      missing credential fails without touching installed content.

Run from anywhere; the repo root is resolved from this file:
    python3 dsh/tests/test_install_presets.py        # python3 + PyYAML
    .venv/bin/python dsh/tests/test_install_presets.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = ROOT / "dsh" / "install-presets.sh"

# (slug, preset display name, preset order, expected bundled skill names)
AGENTS: list[tuple[str, str, int, set[str]]] = [
    (
        "a-share-market-researcher",
        "A股行业研究",
        10,
        {
            "a-share-competitive-analysis",
            "a-share-comps-analysis",
            "a-share-data-sources",
            "a-share-idea-generation",
            "a-share-sector-overview",
            "pptx-author",
        },
    ),
    (
        "a-share-screener",
        "A股短线筛股",
        11,
        {
            "a-share-daily-brief",
            "a-share-event-calendar",
            "a-share-quant-screen",
            "a-share-risk-check",
            "a-share-topic-screen",
        },
    ),
    (
        "earnings-reviewer",
        "财报评审",
        12,
        {"audit-xls", "earnings-analysis", "earnings-preview", "model-update", "morning-note", "xlsx-author"},
    ),
    (
        "market-researcher",
        "行业研究",
        13,
        {"competitive-analysis", "comps-analysis", "idea-generation", "pptx-author", "sector-overview"},
    ),
    (
        "model-builder",
        "金融模型构建",
        14,
        {"3-statement-model", "audit-xls", "comps-analysis", "dcf-model", "lbo-model", "xlsx-author"},
    ),
    (
        "pitch-agent",
        "投行 Pitch",
        15,
        {
            "3-statement-model", "audit-xls", "comps-analysis", "dcf-model", "deck-refresh",
            "ib-check-deck", "lbo-model", "pitch-deck", "pptx-author", "sector-overview", "xlsx-author",
        },
    ),
]

# Rows every preset must mount (mirrors the a-share MVP spec).
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

# The delegation group is intentionally absent for every FSI preset.
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
    """Remove DSH `!!js` tag prefixes so yaml.safe_load can check structure."""
    return re.sub(r"!!js\s+", "", text)


def load_rows(agent_cordis: Path):
    rows = yaml.safe_load(strip_js_tags(agent_cordis.read_text(encoding="utf-8")))
    if not isinstance(rows, list):
        raise AssertionError("agent.cordis.yml 顶层必须是行列表（list of rows）")
    return rows, {row["id"]: row for row in rows if isinstance(row, dict) and "id" in row}


def run_install(home: Path, args: list[str], key: str | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOME"] = str(home)
    if key is None:
        env.pop("DEEPSEEK_API_KEY", None)
    else:
        env["DEEPSEEK_API_KEY"] = key
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def all_agent_cordis_bytes(dest: Path) -> bytes:
    """Concatenated digest of every installed agent.cordis.yml (for idempotency)."""
    paths = [dest / slug / "agent.cordis.yml" for slug, *_ in AGENTS]
    return b"\0".join(p.read_bytes() for p in sorted(paths))


def main() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    check(INSTALL_SH.is_file(), f"缺少安装脚本 {INSTALL_SH.relative_to(ROOT)}")

    for slug, name, order, expected_skills in AGENTS:
        check(
            (ROOT / "plugins" / "agent-plugins" / slug / "skills").is_dir(),
            f"{slug}: 缺 bundled skills 目录",
        )
        check(
            (ROOT / "plugins" / "agent-plugins" / slug / "agents" / f"{slug}.md").is_file(),
            f"{slug}: 缺 persona 源 agents/{slug}.md",
        )
        check(
            (ROOT / "dsh" / "presets" / slug / "preset.yml").is_file(),
            f"{slug}: 缺 preset 源 preset.yml",
        )
        check(
            (ROOT / "dsh" / "presets" / slug / "agent.cordis.yml").is_file(),
            f"{slug}: 缺 preset 源 agent.cordis.yml",
        )

    if failures:
        for msg in failures:
            print("FAIL:", msg)
        return 1

    with tempfile.TemporaryDirectory(prefix="dsh-presets-test-") as tmp:
        home = Path(tmp)

        # ── install, twice, into an isolated HOME ──────────────────────────
        proc1 = run_install(home, ["all"], "ci-dummy-key-presence-check-only")
        check(proc1.returncode == 0, f"install all 退出码 {proc1.returncode}：{proc1.stderr.strip()[-400:]}")
        dest = home / ".dsh" / ".agent-presets"
        first_digest = all_agent_cordis_bytes(dest)

        installed = [p.name for p in dest.iterdir() if p.is_dir()]
        check(
            sorted(installed) == sorted(slug for slug, *_ in AGENTS),
            f"应恰好安装 {len(AGENTS)} 个 preset，实际：{sorted(installed)}",
        )

        proc2 = run_install(home, ["all"], "ci-dummy-key-presence-check-only")
        check(proc2.returncode == 0, f"install 第 2 次退出码 {proc2.returncode}：{proc2.stderr.strip()[-400:]}")
        check(all_agent_cordis_bytes(dest) == first_digest, "重复安装后 agent.cordis.yml 字节不一致（应幂等）")

        # 缺凭据时 install 应明确失败且不改动已装内容
        proc3 = run_install(home, ["all"], None)
        check(proc3.returncode != 0, "缺 DEEPSEEK_API_KEY / credentials.yaml 时 install 应报错退出")
        check("DEEPSEEK_API_KEY" in proc3.stderr, "缺凭据报错应提及 DEEPSEEK_API_KEY")
        check(all_agent_cordis_bytes(dest) == first_digest, "缺凭据失败不应改动已安装内容")

        # ── per-agent contract ─────────────────────────────────────────────
        for slug, name, order, expected_skills in AGENTS:
            agent_cordis = dest / slug / "agent.cordis.yml"
            preset_yml = dest / slug / "preset.yml"
            agent_prefix = f"{slug}:"

            check(agent_cordis.is_file(), f"{agent_prefix} 未生成 agent.cordis.yml")
            check(preset_yml.is_file(), f"{agent_prefix} 未生成 preset.yml")

            # (a) YAML 可解析
            try:
                rows, by_id = load_rows(agent_cordis)
            except Exception as exc:  # noqa: BLE001
                check(False, f"{agent_prefix} YAML 解析失败：{exc}")
                rows, by_id = [], {}

            # (b) persona 逐字节一致
            expected_persona = persona_body(
                (ROOT / "plugins" / "agent-plugins" / slug / "agents" / f"{slug}.md").read_text(encoding="utf-8")
            )
            check(bool(expected_persona), f"{agent_prefix} persona 正文为空")
            persona_row = by_id.get("persona")
            check(persona_row is not None, f"{agent_prefix} 缺 persona 行")
            if persona_row is not None:
                persona_text = (persona_row.get("config") or {}).get("text")
                check(isinstance(persona_text, str) and persona_text, f"{agent_prefix} persona text 为空")
                check(persona_text == expected_persona, f"{agent_prefix} persona text 与 agents/*.md 正文逐字节不一致")

            # (c) customSkillDirs 指向该 agent skills 根且集合正确
            sf_row = by_id.get("skill-filesystem")
            check(sf_row is not None, f"{agent_prefix} 缺 skill-filesystem 行")
            if sf_row is not None:
                cfg = sf_row.get("config") or {}
                check(cfg.get("includeDefaultRoots") is False, f"{agent_prefix} includeDefaultRoots 应为 false")
                dirs = cfg.get("customSkillDirs") or []
                check(len(dirs) == 1, f"{agent_prefix} customSkillDirs 应只有一条")
                if dirs:
                    expr = str(dirs[0])
                    check(expr.startswith("process.cwd()"), f"{agent_prefix} customSkillDirs 应为 process.cwd() 表达式")
                    check(
                        f"plugins/agent-plugins/{slug}/skills" in expr,
                        f"{agent_prefix} customSkillDirs 未指向本 agent skills 目录：{expr!r}",
                    )
            skills_dir = ROOT / "plugins" / "agent-plugins" / slug / "skills"
            present = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
            check(
                present == expected_skills,
                f"{agent_prefix} skills 目录应恰好含 {len(expected_skills)} 个 SKILL.md，实际：{sorted(present)}",
            )

            # (d) 行集合
            row_ids = set(by_id)
            check(EXPECTED_ROWS <= row_ids, f"{agent_prefix} 缺少预期行：{sorted(EXPECTED_ROWS - row_ids)}")
            check(not (FORBIDDEN_ROWS & row_ids), f"{agent_prefix} 不应出现 delegation 行：{sorted(FORBIDDEN_ROWS & row_ids)}")

            # (e) preset 元数据
            meta = yaml.safe_load(preset_yml.read_text(encoding="utf-8"))
            check(isinstance(meta, dict) and meta.get("name") == name, f"{agent_prefix} preset.yml name 应为 {name!r}")
            check(meta.get("order") == order, f"{agent_prefix} preset.yml order 应为 {order}")

            # 源模板保留占位符（install 不得改写仓库源文件）
            check(
                "__PERSONA_TEXT__" in (ROOT / "dsh" / "presets" / slug / "agent.cordis.yml").read_text(encoding="utf-8"),
                f"{agent_prefix} 源模板应保留 __PERSONA_TEXT__ 占位符",
            )

    if failures:
        for msg in failures:
            print("FAIL:", msg)
        return 1

    total_skills = sum(len(sk) for *_ , sk in AGENTS)
    print(
        f"PASS: dsh/install-presets.sh 安装有效性 — {len(AGENTS)} presets / "
        f"{total_skills} skills / {len(EXPECTED_ROWS)} rows each / 幂等"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
