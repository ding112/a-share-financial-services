#!/usr/bin/env python3
"""
Lint all plugin + managed-agent manifests and verify cross-file references.

Checks:
  1. Every *.yaml under managed-agents/ parses.
  2. Every plugin.json / marketplace.json / steering-examples.json parses.
  3. Every <vertical>/agents/*.md has valid YAML frontmatter with name + description.
  4. Every system.file, skills[].path, callable_agents[].manifest in agent.yaml
     and subagent yamls resolves to an existing file/dir.
  5. Every managed-agents/<slug>/ has agent.yaml, README.md, steering-examples.json.
  6. Text files do not use <agent-plugin-slug>:<bundled-skill> as an agent type.
  7. Every Codex-exposed plugin has a matching Codex plugin manifest.
  8. The Codex marketplace only exposes approved skill-package plugins.

Exit 0 if clean, 1 otherwise. Requires: pyyaml.
"""
import json
import re
import sys
from pathlib import Path

from check_a_share_data_contract import validate_contract  # noqa: E402
from check_a_share_idea_generation_contract import (  # noqa: E402
    validate_contract as validate_idea_generation_contract,
)
from check_a_share_comps_artifact_contract import (  # noqa: E402
    validate_contract as validate_comps_artifact_contract,
)
from check_a_share_comps_generator import validate_comps_generator  # noqa: E402
from check_a_share_comps_workbook import validate_comps_workbook  # noqa: E402
from check_a_share_research_handoff import validate_research_handoff  # noqa: E402
from check_a_share_research_note import validate_research_note  # noqa: E402
from check_a_share_dashboard import validate_dashboard  # noqa: E402
from check_a_share_output_layout import validate_output_layout  # noqa: E402
from check_a_share_research_pack_fixtures import validate_fixtures  # noqa: E402
from check_a_share_research_pack_prep import validate_prep_script  # noqa: E402
from check_a_share_public_data_fetcher import validate_public_data_fetcher  # noqa: E402
from check_a_share_auto_prepare import validate_auto_prepare  # noqa: E402
from check_a_share_auxiliary_fetchers import validate_auxiliary_fetchers  # noqa: E402
from check_a_share_annual_report_fetcher import validate_annual_report_fetcher  # noqa: E402
from check_a_share_research_report_fetcher import validate_research_report_fetcher  # noqa: E402
from check_a_share_market_activity_fetcher import validate_market_activity_fetcher  # noqa: E402

try:
    import yaml
except ImportError:
    print("ERROR: requires pyyaml (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
MANAGED = ROOT / "managed-agent-cookbooks"
errors: list[str] = []
checked = 0


def err(msg: str) -> None:
    errors.append(msg)


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        err(f"JSON read: {rel(path)}: {e}")
        return {}
    if not isinstance(payload, dict):
        err(f"JSON shape: {rel(path)}: expected object")
        return {}
    return payload


def version_base(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.split("+", 1)[0]


def agent_plugin_dirs() -> list[Path]:
    root = PLUGINS / "agent-plugins"
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def approved_codex_plugin_dirs() -> dict[str, Path]:
    plugins = {p.name: p for p in agent_plugin_dirs()}
    plugins["equity-research"] = PLUGINS / "vertical-plugins" / "equity-research"
    return plugins


# --- 1. YAML parse ----------------------------------------------------------
for yml in sorted(MANAGED.rglob("*.yaml")):
    checked += 1
    try:
        with open(yml) as f:
            yaml.safe_load(f)
    except yaml.YAMLError as e:
        err(f"YAML parse: {rel(yml)}: {e}")

# --- 2. JSON parse ----------------------------------------------------------
json_globs = [
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "plugins/**/.claude-plugin/plugin.json",
    "plugins/**/.codex-plugin/plugin.json",
    "managed-agent-cookbooks/*/steering-examples.json",
]
for pat in json_globs:
    for jf in sorted(ROOT.glob(pat)):
        checked += 1
        try:
            json.loads(jf.read_text())
        except json.JSONDecodeError as e:
            err(f"JSON parse: {rel(jf)}: {e}")

# --- 3. agent.md frontmatter -----------------------------------------------
for md in sorted(PLUGINS.glob("agent-plugins/*/agents/*.md")):
    checked += 1
    text = md.read_text()
    if not text.startswith("---"):
        err(f"frontmatter: {rel(md)}: missing leading ---")
        continue
    try:
        _, fm, _ = text.split("---", 2)
        meta = yaml.safe_load(fm)
        for k in ("name", "description"):
            if k not in meta:
                err(f"frontmatter: {rel(md)}: missing '{k}'")
    except (ValueError, yaml.YAMLError) as e:
        err(f"frontmatter: {rel(md)}: {e}")


# --- 4. reference resolution -----------------------------------------------
def check_refs(yml: Path) -> None:
    try:
        data = yaml.safe_load(yml.read_text()) or {}
    except yaml.YAMLError:
        return  # already reported above
    base = yml.parent

    sys_spec = data.get("system")
    if isinstance(sys_spec, dict) and "file" in sys_spec:
        p = (base / sys_spec["file"]).resolve()
        if not p.is_file():
            err(f"ref: {rel(yml)}: system.file -> {sys_spec['file']} (not found)")

    for s in data.get("skills") or []:
        if isinstance(s, dict) and "path" in s:
            p = (base / s["path"]).resolve()
            if not p.exists():
                err(f"ref: {rel(yml)}: skills.path -> {s['path']} (not found)")
        if isinstance(s, dict) and "from_plugin" in s:
            p = (base / s["from_plugin"]).resolve()
            if not (p / "skills").is_dir():
                err(f"ref: {rel(yml)}: skills.from_plugin -> {s['from_plugin']} (no skills/ dir)")

    for c in data.get("callable_agents") or []:
        if isinstance(c, dict) and "manifest" in c:
            p = (base / c["manifest"]).resolve()
            if not p.is_file():
                err(f"ref: {rel(yml)}: callable_agents.manifest -> {c['manifest']} (not found)")


for yml in sorted(MANAGED.rglob("*.yaml")):
    check_refs(yml)

# --- 4b. agent-plugin bundled skills match vertical source -----------------
import filecmp  # noqa: E402

src_by_name = {p.name: p for p in PLUGINS.glob("vertical-plugins/*/skills/*") if p.is_dir()}
agent_skills: dict[str, set[str]] = {}
for bundled in sorted(PLUGINS.glob("agent-plugins/*/skills/*")):
    if not bundled.is_dir():
        continue
    slug = bundled.parents[1].name
    agent_skills.setdefault(slug, set()).add(bundled.name)
    src = src_by_name.get(bundled.name)
    if not src:
        err(f"bundled-skill: {rel(bundled)}: no vertical-plugins source named '{bundled.name}'")
        continue
    cmp = filecmp.dircmp(src, bundled, ignore=[".DS_Store"])
    if cmp.diff_files or cmp.left_only or cmp.right_only:
        err(
            f"bundled-skill: {rel(bundled)}: drifted from {rel(src)} "
            f"(run scripts/sync-agent-skills.py)"
        )

# --- 4b2. agent.md skill references exist in the agent's own bundle --------
for md in sorted(PLUGINS.glob("agent-plugins/*/agents/*.md")):
    slug = md.parents[1].name
    sk_dir = PLUGINS / "agent-plugins" / slug / "skills"
    bundle = {p.name for p in sk_dir.iterdir() if p.is_dir()} if sk_dir.is_dir() else set()
    for ref in set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", md.read_text())):
        if ref in src_by_name and ref not in bundle:
            err(
                f"agent-prose: {rel(md)}: references `{ref}` but "
                f"plugins/agent-plugins/{slug}/skills/{ref}/ is not bundled"
            )

# --- 4b3. skill names are not used as agent type suffixes ------------------
TEXT_FILE_SUFFIXES = {".md", ".json", ".yaml", ".yml"}
IGNORED_TEXT_DIRS = {".git", "__pycache__"}
AGENT_TYPE_RE = re.compile(r"\b([a-z0-9]+(?:-[a-z0-9]+)+):([a-z0-9]+(?:-[a-z0-9]+)+)\b")
NEGATED_AGENT_TYPE_MARKERS = (
    "do not use",
    "must not use",
    "should not use",
    "not use",
    "不要",
    "不应",
    "不能",
    "不是",
)


def iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_FILE_SUFFIXES:
            continue
        if any(part in IGNORED_TEXT_DIRS for part in path.parts):
            continue
        yield path


def is_negated_reference(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in NEGATED_AGENT_TYPE_MARKERS)


for text_file in iter_text_files(ROOT):
    try:
        text = text_file.read_text()
    except UnicodeDecodeError:
        continue
    for lineno, line in enumerate(text.splitlines(), start=1):
        if is_negated_reference(line):
            continue
        for match in AGENT_TYPE_RE.finditer(line):
            slug, suffix = match.groups()
            if suffix == slug:
                continue
            if suffix in agent_skills.get(slug, set()):
                err(
                    f"agent-type: {rel(text_file)}:{lineno}: "
                    f"`{slug}:{suffix}` uses bundled skill `{suffix}` as an agent type"
                )

# --- 4c. marketplace source paths resolve ----------------------------------
mp = ROOT / ".claude-plugin" / "marketplace.json"
for p in json.loads(mp.read_text()).get("plugins", []):
    src = (ROOT / p["source"]).resolve()
    if not (src / ".claude-plugin" / "plugin.json").is_file():
        err(f"marketplace: {p['name']} source -> {p['source']} (no plugin.json)")

# --- 4d. Codex plugin manifests match approved skill packages --------------
CODEX_FORBIDDEN_FIELDS = {"agents", "apps", "commands", "hooks", "mcpServers"}

for plugin_name, plugin_dir in approved_codex_plugin_dirs().items():
    claude_manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    codex_manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    if not claude_manifest_path.is_file():
        err(f"codex-manifest: {rel(plugin_dir)}: missing .claude-plugin/plugin.json")
        continue
    if not codex_manifest_path.is_file():
        err(f"codex-manifest: {rel(plugin_dir)}: missing .codex-plugin/plugin.json")
        continue

    claude_manifest = read_json(claude_manifest_path)
    codex_manifest = read_json(codex_manifest_path)
    if codex_manifest.get("name") != plugin_name:
        err(f"codex-manifest: {rel(codex_manifest_path)}: name must match plugin dir")
    for field in ("name", "description"):
        if codex_manifest.get(field) != claude_manifest.get(field):
            err(
                f"codex-manifest: {rel(codex_manifest_path)}: {field} does not match "
                f"{rel(claude_manifest_path)}"
            )

    if version_base(codex_manifest.get("version")) != version_base(claude_manifest.get("version")):
        err(
            f"codex-manifest: {rel(codex_manifest_path)}: version base does not match "
            f"{rel(claude_manifest_path)}"
        )

    forbidden = sorted(CODEX_FORBIDDEN_FIELDS.intersection(codex_manifest))
    if forbidden:
        err(
            f"codex-manifest: {rel(codex_manifest_path)}: Codex skill package v1 must not "
            f"declare {', '.join(forbidden)}"
        )

    if codex_manifest.get("skills") != "./skills/":
        err(f"codex-manifest: {rel(codex_manifest_path)}: skills must be './skills/'")
    if not (plugin_dir / "skills").is_dir():
        err(f"codex-manifest: {rel(plugin_dir)}: skills field present but skills/ is missing")

    interface = codex_manifest.get("interface")
    if not isinstance(interface, dict):
        err(f"codex-manifest: {rel(codex_manifest_path)}: interface must be an object")
        continue
    if interface.get("category") != "Finance":
        err(f"codex-manifest: {rel(codex_manifest_path)}: interface.category must be Finance")
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or "Skills" not in capabilities:
        err(f"codex-manifest: {rel(codex_manifest_path)}: interface.capabilities must include Skills")

# --- 4e. Codex marketplace source paths resolve ----------------------------
codex_mp = ROOT / ".agents" / "plugins" / "marketplace.json"
codex_marketplace = read_json(codex_mp)
if codex_marketplace:
    if codex_marketplace.get("name") != "financial-services":
        err("codex-marketplace: .agents/plugins/marketplace.json: name must be financial-services")

    expected_plugins = set(approved_codex_plugin_dirs())
    entries = codex_marketplace.get("plugins")
    if not isinstance(entries, list):
        err("codex-marketplace: .agents/plugins/marketplace.json: plugins must be an array")
        entries = []
    seen_plugins: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            err("codex-marketplace: .agents/plugins/marketplace.json: plugin entry must be an object")
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            err("codex-marketplace: .agents/plugins/marketplace.json: plugin entry missing name")
            continue
        seen_plugins.add(name)
        if name not in expected_plugins:
            err(f"codex-marketplace: {name}: only approved skill packages may be registered in v1")

        source = entry.get("source")
        if not isinstance(source, dict) or source.get("source") != "local":
            err(f"codex-marketplace: {name}: source must be a local source object")
            continue
        raw_path = source.get("path")
        if not isinstance(raw_path, str):
            err(f"codex-marketplace: {name}: source.path must be a string")
            continue
        src = (ROOT / raw_path).resolve()
        if not (src / ".codex-plugin" / "plugin.json").is_file():
            err(f"codex-marketplace: {name}: source.path -> {raw_path} (no Codex plugin.json)")
        if src.name != name:
            err(f"codex-marketplace: {name}: source.path must point to matching plugin dir")

        policy = entry.get("policy")
        if not isinstance(policy, dict):
            err(f"codex-marketplace: {name}: policy must be an object")
        else:
            if policy.get("installation") != "AVAILABLE":
                err(f"codex-marketplace: {name}: policy.installation must be AVAILABLE")
            if policy.get("authentication") != "ON_INSTALL":
                err(f"codex-marketplace: {name}: policy.authentication must be ON_INSTALL")
        if entry.get("category") != "Finance":
            err(f"codex-marketplace: {name}: category must be Finance")

    missing = sorted(expected_plugins - seen_plugins)
    extra = sorted(seen_plugins - expected_plugins)
    if missing:
        err(f"codex-marketplace: missing plugin entries: {', '.join(missing)}")
    if extra:
        err(f"codex-marketplace: unexpected plugin entries: {', '.join(extra)}")

# --- 5. required files per managed-agent -----------------------------------
for d in sorted(MANAGED.iterdir()):
    if not d.is_dir():
        continue
    for req in ("agent.yaml", "README.md", "steering-examples.json"):
        if not (d / req).is_file():
            err(f"missing: {rel(d)}/{req}")

# --- 6. A-share data source contract ---------------------------------------
for contract_error in validate_contract():
    err(contract_error)

for contract_error in validate_comps_artifact_contract():
    err(contract_error)

# --- 7. A-share idea generation contract -----------------------------------
for contract_error in validate_idea_generation_contract():
    err(contract_error)

for fixture_error in validate_fixtures():
    err(fixture_error)

for prep_error in validate_prep_script():
    err(prep_error)

for public_data_error in validate_public_data_fetcher():
    err(public_data_error)

for auto_prepare_error in validate_auto_prepare():
    err(auto_prepare_error)

for auxiliary_fetcher_error in validate_auxiliary_fetchers():
    err(auxiliary_fetcher_error)

for annual_report_fetcher_error in validate_annual_report_fetcher():
    err(annual_report_fetcher_error)

for research_report_fetcher_error in validate_research_report_fetcher():
    err(research_report_fetcher_error)

for market_activity_fetcher_error in validate_market_activity_fetcher():
    err(market_activity_fetcher_error)

for generator_error in validate_comps_generator():
    err(generator_error)

for workbook_error in validate_comps_workbook():
    err(workbook_error)

for handoff_error in validate_research_handoff():
    err(handoff_error)

for note_error in validate_research_note():
    err(note_error)

for dashboard_error in validate_dashboard():
    err(dashboard_error)

for output_layout_error in validate_output_layout():
    err(output_layout_error)

# --- report ----------------------------------------------------------------
if errors:
    print(f"FAIL — {len(errors)} issue(s) across {checked} file(s):\n", file=sys.stderr)
    for e in errors:
        print(f"  ✗ {e}", file=sys.stderr)
    sys.exit(1)
print(f"OK — {checked} file(s) checked, 0 issues.")
