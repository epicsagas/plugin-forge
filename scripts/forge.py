#!/usr/bin/env python3
"""forge.py — multi-host plugin manager (create / doctor / install / publish).

Cross-platform (Windows / Linux / macOS). Standard library only.
Hosts: claude (Claude Code), codex (Codex), agy (Antigravity CLI),
       hermes (Nous Research Hermes Agent), grok (xAI Grok Build).

Manifest pattern (toefl-prep / byoh):
  plugin.json (root)               -> agy
  plugin.yaml (root)               -> hermes (YAML manifest)
  .claude-plugin/plugin.json       -> Claude Code (skills/commands/agents)
  .claude-plugin/marketplace.json  -> Claude marketplace (source "./")
  .codex-plugin/plugin.json        -> Codex (interface block)
  .agents/plugins/marketplace.json -> Codex standalone catalog (local path
                                      ./plugins/<name>, not "./")
  .grok-plugin/plugin.json         -> grok metadata manifest (components are
                                      read natively from the plugin root)
  .claude/skills, .codex/skills, .hermes/skills -> dir symlinks to ../skills
  .claude/agents -> ../agents (dir symlink); codex agents are NATIVE TOML
  under .codex-plugin/agents/<n>.toml, linked from .codex/agents
  .mcp.json (root, grok)           -> file symlink to mcp_config.json

Usage:
  python3 forge.py create   <name> [--owner LOGIN] [--hosts ...] [--desc "..."] [--dir PATH]
  python3 forge.py doctor   [PATH] [--fix] [--owner LOGIN]
  python3 forge.py install  <PATH>  [--host claude|codex|agy|hermes|grok|all] [--keep]
  python3 forge.py publish  [PATH]  [--owner LOGIN] [--marketplace [OWNER/REPO]] [--no-push]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, textwrap
from pathlib import Path

VERSION = "0.2.1"
# Version stamped into a NEWLY created plugin. Kept separate from VERSION so
# forge's own version never leaks into generated manifests.
INITIAL_VERSION = "0.1.0"
SCRIPT_DIR = Path(__file__).resolve().parent
TPL_DIR = SCRIPT_DIR / "templates"
# GitHub owner / optional hub catalog. Empty by default — never assume the
# forge author's org. Set --owner / PLUGIN_FORGE_OWNER, and for hub registration
# --marketplace OWNER/REPO or PLUGIN_FORGE_MARKETPLACE.
OWNER_PLACEHOLDER = "YOUR_GITHUB_USER"
_GH_REMOTE_RE = re.compile(
    r"(?:github\.com[:/])(?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?(?:\s|$)"
)


def _env(key: str) -> str:
    return (os.environ.get(key) or "").strip()


def resolve_owner(args=None) -> str:
    if args is not None:
        v = (getattr(args, "owner", None) or "").strip()
        if v:
            return v
    return _env("PLUGIN_FORGE_OWNER")


def resolve_hub(args=None) -> str:
    """Optional extra catalog (a hub). Independent plugins do not need one."""
    if args is not None:
        mp = getattr(args, "marketplace", None)
        if isinstance(mp, str) and "/" in mp.strip():
            return mp.strip()
    return _env("PLUGIN_FORGE_MARKETPLACE")


def owner_from_git(path: Path) -> str:
    r = run(["git", "-C", str(path), "remote", "get-url", "origin"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if r.returncode != 0:
        return ""
    m = _GH_REMOTE_RE.search((r.stdout or "").strip())
    return m.group("owner") if m else ""

# Each host reads a DIFFERENT marketplace manifest. Registering only the Claude
# one leaves the plugin invisible to `codex plugin add` with no error at
# publish time, so every host catalog is kept in sync.
MARKETPLACE_MANIFESTS = {
    "claude": ".claude-plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
    # grok catalog entries pin the upstream commit (40-hex sha); Grok Build
    # re-verifies `git rev-parse HEAD == sha` after cloning, so a registration
    # without the pushed sha is rejected (see register_marketplace).
    "grok": ".grok-plugin/marketplace.json",
    # hermes uses one plugin.yaml per plugin instead of a shared list
    "hermes": ".hermes/{name}/plugin.yaml",
}

# Lifecycle hook config location per host. Claude and Codex BOTH default to
# hooks/hooks.json, so a plugin shipping that generic path is ambiguous —
# doctor flags it.
HOOK_FILES = {
    "claude": ".claude-plugin/hooks.json",
    "codex": ".codex-plugin/hooks.json",
    "agy": "hooks.json",
    # hooks/hooks.json is grok's SPEC location — but also the DEFAULT for both
    # claude and codex, so it is only accepted when grok is a selected host.
    "grok": "hooks/hooks.json",
}
AMBIGUOUS_HOOK_FILE = "hooks/hooks.json"
# hermes has no hook FILE — callbacks are registered in __init__.py via
# ctx.register_hook(name, fn). Names are checked against hermes' VALID_HOOKS;
# an unknown name only logs a warning at runtime, so it fails silently.
HERMES_HOOK_EVENTS = {
    "api_request_error", "kanban_task_blocked", "kanban_task_claimed",
    "kanban_task_completed", "on_session_end", "on_session_finalize",
    "on_session_reset", "on_session_start", "post_api_request",
    "post_approval_response", "post_llm_call", "post_tool_call",
    "pre_api_request", "pre_approval_request", "pre_gateway_dispatch",
    "pre_llm_call", "pre_tool_call", "pre_verify", "subagent_start",
    "subagent_stop", "transform_llm_output", "transform_terminal_output",
    "transform_tool_result",
}
# Real plugins pass the name from a collection (EVENTS = [...] / {...: ...}),
# never a literal, so a register_hook("literal") regex never matches. Instead
# look at hook-SHAPED string literals anywhere in the file. Restricting to the
# known prefixes keeps unrelated strings ("working", "claude code") out.
_HOOK_LITERAL_RE = re.compile(
    r'["\']((?:pre|post|on|transform|subagent|kanban|api)_[a-z_]+)["\']')
# Events each host actually supports (used to catch cross-host copy/paste).
HOST_HOOK_EVENTS = {
    "claude": {"PreToolUse", "PostToolUse", "UserPromptSubmit", "Notification",
               "Stop", "SubagentStop", "SessionStart", "SessionEnd", "PreCompact",
               "PermissionRequest", "PostToolUseFailure", "StopFailure"},
    "codex": {"PreToolUse", "PostToolUse", "PermissionRequest", "PreCompact",
              "PostCompact", "SessionStart", "SessionEnd", "SubagentStart",
              "SubagentStop", "UserPromptSubmit", "Stop"},
    "agy": {"PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"},
}

VALID_HOSTS = ("claude", "codex", "agy", "hermes", "grok")
# grok (Grok Build, xAI) metadata manifest. The plugin's components (skills/,
# commands/, agents/) are read natively from the plugin root — no discovery
# symlink needed. xAI publishes no $schema URL, so it is validated like the
# codex manifest (plain JSON + name consistency). Reference:
# https://github.com/xai-org/plugin-marketplace
GROK_PLUGIN_MANIFEST = ".grok-plugin/plugin.json"
# xAI remote catalog entries must pin a full lowercase 40-hex commit.
GROK_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MANIFEST_SCHEMAS = {
    "plugin.json": "https://antigravity.google/schemas/v1/plugin.json",
    ".claude-plugin/plugin.json": "https://json.schemastore.org/claude-code-plugin-manifest.json",
    ".claude-plugin/marketplace.json": "https://anthropic.com/claude-code/marketplace.schema.json",
}
REQUIRED_FIELDS = ("name", "version", "description")
# A slash command is an ENTRY POINT, not a second spec. Anything past a few
# lines of "invoke the skill with $ARGUMENTS" duplicates SKILL.md and drifts
# out of sync the next time a host is added.
COMMAND_BODY_MAX_LINES = 8
# hermes uses a YAML manifest (plugin.yaml) — required top-level keys (same set).
HERMES_MANIFEST = "plugin.yaml"
HERMES_REQUIRED = ("name", "version", "description")
# stdlib-only YAML top-level key extractor (no PyYAML dependency).
# Matches column-0 'key: value' / 'key: "value"' / 'key:' lines only.
_YAML_KEY_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.*)$')


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def is_valid_json(p: Path) -> bool:
    return load_json(p) is not None


def load_yaml_keys(p: Path) -> dict | None:
    """stdlib-only YAML top-level key extract (no PyYAML).

    Returns a {key: raw_value_str} dict of column-0 mappings, or None on read
    failure. Only top-level keys (indent 0) are captured — nested mappings under
    a key are ignored. This is enough to validate the required manifest fields
    and check name consistency without a YAML dependency.
    """
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return None
    keys: dict[str, str] = {}
    for line in text.splitlines():
        # skip comments / blank / indented lines
        if not line or line[0] in (" ", "\t", "#"):
            continue
        m = _YAML_KEY_RE.match(line)
        if m:
            k, v = m.group(1), m.group(2).strip()
            # strip inline comments and surrounding quotes
            if "#" in v:
                v = v.split("#", 1)[0].strip()
            v = v.strip().strip('"').strip("'")
            keys[k] = v
    return keys


def is_valid_hermes_manifest(p: Path) -> bool:
    keys = load_yaml_keys(p)
    if keys is None:
        return False
    return all(k in keys for k in HERMES_REQUIRED)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(tpl: Path, out: Path, **kw) -> None:
    text = tpl.read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace(f"__{k.upper()}__", str(v))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def ensure_dirlink(link: Path, rel_target: str) -> None:
    """Make `link` a DIRECTORY symlink to `rel_target`, replacing any copy.

    One symlink per host folder. The root skills/ and agents/ dirs are the
    single source of truth; per-file links or real copies are how host trees
    drift into duplicated skills.
    """
    if link.is_symlink() and os.readlink(link) == rel_target:
        return
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.is_dir():
        shutil.rmtree(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(rel_target, link)


def ensure_codex_plugin_bundle(path: Path, name: str) -> None:
    """Expose the plugin at plugins/<name> via dirlinks.

    Codex rejects local catalog paths that resolve to the marketplace root
    (".", "./"). A subdirectory of dirlinks keeps one copy of skills/agents
    without a parent-symlink cycle.
    """
    bundle = path / "plugins" / name
    bundle.mkdir(parents=True, exist_ok=True)
    ensure_dirlink(bundle / ".codex-plugin", "../../.codex-plugin")
    if (path / "skills").is_dir():
        ensure_dirlink(bundle / "skills", "../../skills")
    if (path / "commands").is_dir():
        ensure_dirlink(bundle / "commands", "../../commands")
    if (path / "agents").is_dir():
        ensure_dirlink(bundle / "agents", "../../agents")
    mcp = path / "mcp_config.json"
    if mcp.is_file() or mcp.is_symlink():
        ensure_dirlink(bundle / "mcp_config.json", "../../mcp_config.json")
    legacy = path / ".mcp.json"
    if legacy.exists() or legacy.is_symlink():
        ensure_dirlink(bundle / ".mcp.json", "../../.mcp.json")


def plugin_desc(path: Path, name: str) -> str:
    for rel in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
                GROK_PLUGIN_MANIFEST, "plugin.json"):
        d = load_json(path / rel) or {}
        if d.get("description"):
            return str(d["description"])
    return name


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kw)


def gh_available() -> bool:
    return shutil.which("gh") is not None


def gh_ok(*args: str) -> bool:
    return run(["gh", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def gh_json(*args: str):
    r = run(["gh", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return r.stdout.strip()


def register_marketplace(mpl: Path, name: str, repo: str, desc: str, version: str,
                         sha: str | None = None, owner: str = "",
                         hub: str = "", plugin: Path | None = None) -> list[str]:
    """Register the plugin in every host's marketplace manifest.

    Claude reads .claude-plugin/marketplace.json, Codex reads
    .agents/plugins/marketplace.json, and hermes reads one plugin.yaml per
    plugin. Registering only Claude's leaves `codex plugin add` failing with
    "not found in marketplace" even though publish reported success.
    grok reads .grok-plugin/marketplace.json and REQUIRES the entry's source
    to pin the pushed commit sha (Grok Build re-verifies HEAD == sha after
    cloning), so a grok registration without a sha is skipped with a warning.
    If the catalog file is missing, it is created (name/owner derived from the
    hub repo: the clone lives in a temp dir, so its dirname is meaningless);
    a new entry prefers the plugin's .grok-plugin/plugin.json keywords/category.
    A hermes plugin.yaml stub is only written when the plugin actually ships a
    hermes manifest (root plugin.yaml) — otherwise hermes install would fail
    on the repo — and the skip is reported as "hermes:SKIP". An existing stub
    still gets its version refreshed.
    """
    changed: list[str] = []
    src = {"source": "url", "url": f"https://github.com/{repo}.git"}

    # --- claude ---
    mf = mpl / MARKETPLACE_MANIFESTS["claude"]
    if mf.is_file():
        m = load_json(mf) or {"plugins": []}
        if not any(x.get("name") == name for x in m.get("plugins", [])):
            m.setdefault("plugins", []).append(
                {"name": name, "source": src, "description": desc})
            mf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed.append("claude")

    # --- codex (needs pluginManifest / policy / category) ---
    cf = mpl / MARKETPLACE_MANIFESTS["codex"]
    if cf.is_file():
        m = load_json(cf) or {"plugins": []}
        if not any(x.get("name") == name for x in m.get("plugins", [])):
            m.setdefault("plugins", []).append({
                "name": name,
                "source": src,
                "pluginManifest": "./.codex-plugin/plugin.json",
                "policy": {"installation": "INSTALLED_BY_DEFAULT",
                           "authentication": "ON_INSTALL"},
                "category": "Productivity",
            })
            cf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed.append("codex")
    else:
        changed.append("codex:MISSING")

    # --- grok (sha-pinned remote source; create the catalog file if missing) ---
    gf = mpl / MARKETPLACE_MANIFESTS["grok"]
    if not sha:
        changed.append("grok:NEEDS_SHA")
    else:
        if gf.is_file():
            m = load_json(gf) or {"plugins": []}
        else:
            gf.parent.mkdir(parents=True, exist_ok=True)
            hub_owner = (hub.split("/")[0] if "/" in hub else "") or owner
            m = {
                "name": hub.split("/")[-1],
                "description": "Plugin marketplace",
                "owner": {"name": hub_owner} if hub_owner else {},
                "plugins": [],
            }
        entry = next((x for x in m.get("plugins", []) if x.get("name") == name), None)
        if entry is None:
            gmeta = (load_json(plugin / GROK_PLUGIN_MANIFEST) if plugin else None) or {}
            m.setdefault("plugins", []).append({
                "name": name,
                "description": desc,
                "version": version,
                "category": gmeta.get("category") or "development",
                "source": {"source": "url",
                           "url": f"https://github.com/{repo}.git",
                           "sha": sha},
                "homepage": f"https://github.com/{repo}",
                "keywords": gmeta.get("keywords") or [name],
            })
            gf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed.append("grok")
        elif isinstance(entry.get("source"), dict) and entry["source"].get("sha") != sha:
            # bump the pin to the pushed HEAD (xai-org does this with
            # scripts/bump-plugin-shas.py; same result, in place)
            entry["source"]["sha"] = sha
            gf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed.append(f"grok:sha={sha[:8]}")

    # --- hermes (one plugin.yaml per plugin) ---
    hf = mpl / MARKETPLACE_MANIFESTS["hermes"].format(name=name)
    if (mpl / ".hermes").is_dir():
        if hf.is_file():
            # version refresh: hermes plugin.yaml is the only marketplace
            # manifest that carries a version — claude/codex entries resolve
            # it from the plugin repo at install time.
            keys = load_yaml_keys(hf) or {}
            if keys.get("version") != version:
                text = hf.read_text(encoding="utf-8")
                text = re.sub(r'(?m)^version:[^\n]*$', f'version: "{version}"',
                              text, count=1)
                hf.write_text(text, encoding="utf-8")
                changed.append(f"hermes:version={version}")
        elif plugin and (plugin / HERMES_MANIFEST).is_file():
            hf.parent.mkdir(parents=True, exist_ok=True)
            hf.write_text(
                f'name: {name}\nversion: "{version}"\ndescription: {desc}\n'
                f'provides_skills:\n  - {name}\n', encoding="utf-8")
            changed.append("hermes")
        else:
            # the plugin ships no hermes manifest (root plugin.yaml), so a hub
            # stub would point hermes at a repo it cannot install: dead entry
            changed.append("hermes:SKIP")
    return changed


# ============================================================ create =========
def cmd_create(args) -> int:
    name = args.name
    if not name.replace("-", "").isalnum() or not name.islower() or name != name.lower():
        die("name must be lowercase-kebab (^[a-z0-9-]+$)")
    hosts = [h for h in (args.hosts.split(",") if args.hosts else []) if h] or list(VALID_HOSTS)
    for h in hosts:
        if h not in VALID_HOSTS:
            die(f"unknown host: {h} ({'|'.join(VALID_HOSTS)})")
    disp = args.display_name or name
    owner = resolve_owner(args) or OWNER_PLACEHOLDER
    target = Path(args.dir).expanduser() / name if args.dir else Path.cwd() / name
    target.mkdir(parents=True, exist_ok=True)
    print(f"🔨 Creating plugin '{name}' (hosts: {','.join(hosts)}) -> {target}")
    if owner == OWNER_PLACEHOLDER:
        print(f"  WARN: --owner / PLUGIN_FORGE_OWNER unset; wrote {OWNER_PLACEHOLDER} "
              f"in author/install URLs. Replace before publish.")

    ctx = dict(NAME=name, DESC=args.desc, DISPLAYNAME=disp, OWNER=owner, VERSION=INITIAL_VERSION)

    # source of truth skill
    skill_dir = target / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    # commands/ ships a README, not a .gitkeep: the empty dir is exactly where
    # a session starts inventing a fat second spec. State the rule at the site.
    (target / "commands").mkdir(exist_ok=True)
    (target / "commands" / "README.md").write_text(textwrap.dedent(f"""\
        # commands/

        Slash commands are **entry points, not a second spec**. Each file stays a
        thin delegate: frontmatter (`description`, `argument-hint`, `allowed-tools`)
        plus one line telling the model to invoke the `{name}` skill with `$ARGUMENTS`.

        Never copy the skill's arguments docs, checklists, or host lists here —
        `skills/{name}/SKILL.md` is the single source of truth, and duplicated
        content silently drifts out of sync. `forge.py doctor` WARNs on any command
        whose body exceeds {COMMAND_BODY_MAX_LINES} lines or never mentions the skill.

        Template:

        ```markdown
        ---
        description: One line, shown in the slash menu.
        argument-hint: "<args>"
        allowed-tools: Bash
        ---

        Invoke the `{name}` skill and run its **<action>** action with: $ARGUMENTS
        ```
    """), encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(textwrap.dedent(f"""\
        ---
        name: {name}
        description: >-
          TODO: one-line description of when this skill triggers. Replace this stub.
        ---

        # {name}

        > TODO: describe the workflow. This SKILL.md is the authoritative source;
        > host-discovery dirs (.claude/skills, .codex/skills, .hermes/skills) are
        > symlinks to ../skills, so edits here appear everywhere (forge doctor
        > re-links them if a copy ever replaces a link).

        ## Intents -> actions

        | User intent | Action |
        |-------------|--------|
        | TODO | TODO |
    """), encoding="utf-8")

    # MCP single source of truth: root mcp_config.json (the agy/Antigravity
    # plugin spec name, so agy auto-discovers it with zero wiring). Claude and
    # codex manifests point at the same file; no copies, no symlinks.
    if args.mcp:
        (target / "mcp_config.json").write_text(json.dumps(
            {"mcpServers": {name: {"command": "TODO", "args": []}}},
            indent=2) + "\n", encoding="utf-8")

    if "agy" in hosts:
        render(TPL_DIR / "plugin.json.agy.tpl", target / "plugin.json", **ctx)
    if "claude" in hosts:
        render(TPL_DIR / "plugin.json.claude.tpl", target / ".claude-plugin" / "plugin.json", **ctx)
        render(TPL_DIR / "marketplace.json.tpl", target / ".claude-plugin" / "marketplace.json", **ctx)
        ensure_dirlink(target / ".claude" / "skills", "../skills")
        if (target / "agents").is_dir():
            ensure_dirlink(target / ".claude" / "agents", "../agents")
        if args.mcp:
            mf = target / ".claude-plugin" / "plugin.json"
            d = load_json(mf) or {}
            d["mcpServers"] = ["./mcp_config.json"]
            mf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "codex" in hosts:
        render(TPL_DIR / "plugin.json.codex.tpl", target / ".codex-plugin" / "plugin.json", **ctx)
        ensure_dirlink(target / ".codex" / "skills", "../skills")
        # Codex catalog is .agents/plugins/marketplace.json, not
        # .codex-plugin/marketplace.json. Local path "./" is rejected, so the
        # plugin root is exposed at plugins/<name> via dirlinks.
        ensure_codex_plugin_bundle(target, name)
        render(TPL_DIR / "marketplace.json.codex.tpl",
               target / MARKETPLACE_MANIFESTS["codex"], **ctx)
        if args.mcp:
            mf = target / ".codex-plugin" / "plugin.json"
            d = load_json(mf) or {}
            d["mcpServers"] = "./mcp_config.json"
            mf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            ensure_codex_plugin_bundle(target, name)
    if "grok" in hosts:
        render(TPL_DIR / "plugin.json.grok.tpl", target / GROK_PLUGIN_MANIFEST, **ctx)
        # no standalone .grok-plugin/marketplace.json: Grok Build's browser does
        # not list self-referencing local "." catalogs (measured on 1.0.13,
        # plugin_count=0). Grok delivery is direct install, or a hub's
        # sha-pinned catalog via publish --marketplace.
        # grok reads skills/commands/agents natively from the plugin root —
        # no discovery symlink. Its MCP file IS root .mcp.json, so the agy-named
        # truth gets a file-symlink twin (ensure_dirlink mechanics are
        # path-generic: unlink/copy-dir/rmtree then symlink).
        if args.mcp:
            ensure_dirlink(target / ".mcp.json", "mcp_config.json")
            if "codex" in hosts:
                ensure_codex_plugin_bundle(target, name)
    if "hermes" in hosts:
        render(TPL_DIR / "plugin.yaml.hermes.tpl", target / HERMES_MANIFEST, **ctx)
        # hermes requires __init__.py with register(ctx) to load the plugin dir.
        # Ship a minimal stub that registers bundled skills via ctx.register_skill(),
        # so the plugin is loadable out of the box (see Hermes plugin spec).
        (target / "__init__.py").write_text(textwrap.dedent(f"""\
            \"\"\"{name} — Hermes plugin entry point.

            Hermes loads this module from ~/.hermes/plugins/{name}/ and calls
            register(ctx) once at startup. Bundled skills under skills/ are
            registered here so the agent can load them via skill_view("{name}:<skill>").
            \"\"\"
            from pathlib import Path


            def register(ctx):
                \"\"\"Register bundled skills with the Hermes plugin manager.\"\"\"
                skills_dir = Path(__file__).parent / "skills"
                for child in sorted(skills_dir.iterdir()):
                    skill_md = child / "SKILL.md"
                    if child.is_dir() and skill_md.exists():
                        ctx.register_skill(child.name, skill_md)
        """), encoding="utf-8")
        ensure_dirlink(target / ".hermes" / "skills", "../skills")

    (target / "AGENTS.md").write_text(textwrap.dedent(f"""\
        # AGENTS.md — {name}

        > Shared agent guide. Claude Code, Codex, agy, hermes, and grok all load this file.

        ## Role

        TODO: describe what this plugin does. The authoritative workflow is
        `skills/{name}/SKILL.md`; host-discovery dirs (`.claude/skills`,
        `.codex/skills`, `.hermes/skills`) are symlinks to the root `skills/`.
        Agents live in root `agents/*.md` (Claude) and are converted to
        Codex-native TOML under `.codex-plugin/agents/`.

        ## Host differences

        - All hosts follow `skills/{name}/SKILL.md` (intent->action table).
        - `commands/`, if you add any, are thin delegates to the SKILL — never
          duplicate the skill's arguments docs or checklists there.
    """), encoding="utf-8")

    (target / "README.md").write_text(textwrap.dedent(f"""\
        # {name}

        > TODO: replace this stub README. Multi-host plugin (Claude Code · Codex · agy · hermes · grok).

        ## Install

        ```bash
        # Claude Code (this repo is the marketplace)
        claude plugin marketplace add {owner}/{name}
        claude plugin install {name}@{name}

        # Codex (this repo is the marketplace)
        codex plugin marketplace add {owner}/{name}
        codex plugin add {name}@{name}

        # agy (repo URL, no .git)
        agy plugin install https://github.com/{owner}/{name}
        agy plugin enable {name}

        # hermes (repo URL)
        hermes plugins install https://github.com/{owner}/{name}
        hermes plugins enable {name}
        # Blocked by skills_guard (AGENTS.md mention → CRITICAL persistence)?
        # Disable the install scan in hermes config: plugins.scan_on_install: false

        # grok (Grok Build)
        grok plugin install {owner}/{name} --trust
        ```

        ## License

        MIT
    """), encoding="utf-8")

    (target / "LICENSE").write_text(textwrap.dedent(f"""\
        MIT License

        Copyright (c) 2026 {owner}

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.
    """), encoding="utf-8")

    (target / ".gitignore").write_text(".DS_Store\n*.pyc\n__pycache__/\nscratch/\n*-workspace/\n", encoding="utf-8")

    print(f"\n✓ Created. Files:")
    for f in sorted(target.rglob("*")):
        if f.is_file():
            print(f"  ./{f.relative_to(target)}")
    print(f"\nNext: edit skills/{name}/SKILL.md, then:\n  forge.py doctor {target}\n  forge.py publish {target} --owner LOGIN")
    return 0


def check_grok_catalog(path: Path, emit) -> None:
    """Validate .grok-plugin/marketplace.json against the xAI catalog rules.

    Remote entries need a 40-hex sha; local entries need a path that exists.
    Catalog `name` is the marketplace id, not the plugin id, so it is never
    compared to the plugin name.
    """
    gf = path / MARKETPLACE_MANIFESTS["grok"]
    if not gf.is_file():
        # absence is normal: create stopped generating standalone catalogs
        # (the grok browser does not list self-referencing local "." catalogs).
        # A file that does exist is still validated below (legacy support).
        return
    m = load_json(gf)
    if m is None:
        emit("FAIL", "grok: .grok-plugin/marketplace.json invalid JSON")
        return
    plugins = m.get("plugins")
    if not isinstance(plugins, list):
        emit("FAIL", "grok: marketplace.json missing plugins[] array")
        return
    if not plugins:
        emit("WARN", "grok: marketplace.json has empty plugins[]")
        return
    for i, entry in enumerate(plugins):
        if not isinstance(entry, dict) or not entry.get("name"):
            emit("FAIL", f"grok: plugins[{i}] missing name")
            continue
        src = entry.get("source")
        label = entry["name"]
        if not isinstance(src, dict):
            emit("FAIL", f"grok: catalog {label} missing source object")
            continue
        if src.get("type") == "local":
            pth = src.get("path")
            if not pth:
                emit("FAIL", f"grok: catalog {label} local source missing path")
            elif str(pth).strip("./") == "":
                # self-referencing root: the browser scans the catalog repo
                # itself, so a "." entry resolves inside the scan and is
                # dropped (measured on 1.0.13: plugin_count=0). Local sources
                # are for vendored subdirectories only; pin a remote sha
                # instead (see register_marketplace).
                emit("WARN", f"grok: catalog {label} local path {pth!r} is the "
                             f"catalog root: the grok browser does not list "
                             f"self-referencing catalogs; use a remote "
                             f"url+sha source")
            elif (path / str(pth)).exists():
                emit("PASS", f"grok: catalog {label} local path {pth}")
            else:
                emit("FAIL", f"grok: catalog {label} local path {pth} not found")
        else:
            url = src.get("url")
            sha = src.get("sha")
            if not url:
                emit("FAIL", f"grok: catalog {label} remote source missing url")
            if not isinstance(sha, str) or not GROK_SHA_RE.match(sha):
                emit("FAIL", f"grok: catalog {label} remote source needs 40-hex sha")
            elif url:
                emit("PASS", f"grok: catalog {label} sha-pinned")


CODEX_ROOT_PATHS = {".", "./", "./.", ""}


def check_codex_catalog(path: Path, name: str, emit, fix: bool = False) -> None:
    """Validate .agents/plugins/marketplace.json for a standalone Codex catalog.

    Codex does not read .codex-plugin/marketplace.json. Local source path
    "./" (the marketplace root) is rejected, so standalone plugins expose
    themselves at ./plugins/<name>.
    """
    bogus = path / ".codex-plugin" / "marketplace.json"
    if bogus.is_file():
        emit("WARN", "codex: .codex-plugin/marketplace.json is not read; "
                     "catalog is .agents/plugins/marketplace.json")
    cf = path / MARKETPLACE_MANIFESTS["codex"]
    codex_selected = (path / ".codex-plugin" / "plugin.json").is_file()
    if not cf.is_file():
        if not codex_selected:
            return
        emit("WARN", "codex: no .agents/plugins/marketplace.json "
                     "(codex plugin marketplace add cannot see this repo)")
        if fix:
            d = load_json(path / ".codex-plugin" / "plugin.json") or {}
            display = (d.get("interface") or {}).get("displayName") or name
            ensure_codex_plugin_bundle(path, name)
            render(TPL_DIR / "marketplace.json.codex.tpl", cf,
                   NAME=name, DESC=plugin_desc(path, name), DISPLAYNAME=display)
            emit("PASS", "codex: .agents/plugins/marketplace.json written (--fix)")
        return
    m = load_json(cf)
    if m is None:
        emit("FAIL", "codex: .agents/plugins/marketplace.json invalid JSON")
        return
    plugins = m.get("plugins")
    if not isinstance(plugins, list):
        emit("FAIL", "codex: marketplace.json missing plugins[] array")
        return
    if not plugins:
        emit("WARN", "codex: marketplace.json has empty plugins[]")
        return
    rewritten = False
    for i, entry in enumerate(plugins):
        if not isinstance(entry, dict) or not entry.get("name"):
            emit("FAIL", f"codex: plugins[{i}] missing name")
            continue
        label = entry["name"]
        src = entry.get("source")
        pth = None
        if isinstance(src, str):
            pth = src
        elif isinstance(src, dict) and src.get("source") in (None, "local"):
            pth = src.get("path")
        elif isinstance(src, dict) and src.get("type") == "local":
            pth = src.get("path")
        if pth is not None:
            if pth in CODEX_ROOT_PATHS:
                emit("FAIL", f"codex: catalog {label} local path {pth!r} is the "
                             f"repo root (Codex rejects it); use ./plugins/{name}")
                if fix:
                    ensure_codex_plugin_bundle(path, name)
                    entry["source"] = {"source": "local",
                                       "path": f"./plugins/{name}"}
                    rewritten = True
                    emit("PASS", f"codex: catalog {label} path rewritten "
                                 f"to ./plugins/{name} (--fix)")
            elif not str(pth).startswith("./"):
                emit("FAIL", f"codex: catalog {label} local path {pth!r} "
                             f"must start with './'")
            elif (path / str(pth)).exists():
                emit("PASS", f"codex: catalog {label} local path {pth}")
            else:
                emit("FAIL", f"codex: catalog {label} local path {pth} not found")
                if fix:
                    ensure_codex_plugin_bundle(path, name)
                    if (path / str(pth)).exists():
                        emit("PASS", f"codex: plugins/{name} bundle linked (--fix)")
        pol = entry.get("policy") if isinstance(entry.get("policy"), dict) else {}
        if not pol.get("installation") or not pol.get("authentication"):
            emit("WARN", f"codex: catalog {label} missing policy.installation "
                         f"or policy.authentication")
        if not entry.get("category"):
            emit("WARN", f"codex: catalog {label} missing category")
    if rewritten:
        cf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")


# ============================================================ doctor ========
def cmd_doctor(args) -> int:
    path = Path(args.path)
    if not path.is_dir():
        die(f"path not found: {path}")
    # infer name
    name = ""
    for rel in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json",
                GROK_PLUGIN_MANIFEST, HERMES_MANIFEST):
        if rel == HERMES_MANIFEST:
            d = load_yaml_keys(path / rel)
        else:
            d = load_json(path / rel)
        if d and d.get("name"):
            name = d["name"]
            break
    if not name:
        die(f"cannot determine plugin name (no manifest in {path})")

    fix = args.fix
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}

    def emit(level, msg):
        if level in counts:
            counts[level] += 1
        print(f"{level:<6} {msg}")

    print(f"🩺 forge doctor — {name} ({path})\n")

    # 1. manifest validity + schema + name consistency
    for rel, want_schema in MANIFEST_SCHEMAS.items():
        f = path / rel
        if f.is_file():
            d = load_json(f)
            if d is None:
                emit("FAIL", f"manifest {rel} invalid JSON")
                continue
            got = d.get("$schema", "")
            if not got or got == want_schema:
                emit("PASS", f"manifest {rel} valid")
            else:
                emit("WARN", f"manifest {rel} schema mismatch (got {got or 'none'}, want {want_schema})")
            mn = d.get("name", "")
            if rel != ".claude-plugin/marketplace.json" and mn and mn != name:
                emit("FAIL", f"manifest {rel} name='{mn}' != '{name}'")
    # codex manifest (no strict schema)
    codex = path / ".codex-plugin" / "plugin.json"
    if codex.is_file():
        if load_json(codex) is not None:
            emit("PASS", "manifest .codex-plugin/plugin.json valid")
            mn = (load_json(codex) or {}).get("name", "")
            if mn and mn != name:
                emit("FAIL", f"codex manifest name='{mn}' != '{name}'")
        else:
            emit("FAIL", "manifest .codex-plugin/plugin.json invalid JSON")
    # grok manifest (plain JSON; xAI publishes no $schema URL)
    grok_manifest = path / GROK_PLUGIN_MANIFEST
    if grok_manifest.is_file():
        d = load_json(grok_manifest)
        if d is None:
            emit("FAIL", f"manifest {GROK_PLUGIN_MANIFEST} invalid JSON")
        else:
            emit("PASS", f"manifest {GROK_PLUGIN_MANIFEST} valid")
            mn = d.get("name", "")
            if mn and mn != name:
                emit("FAIL", f"grok manifest name='{mn}' != '{name}'")
    check_grok_catalog(path, emit)
    check_codex_catalog(path, name, emit, fix=fix)
    # hermes manifest (YAML — stdlib key extract, no PyYAML)
    hermes_manifest = path / HERMES_MANIFEST
    if hermes_manifest.is_file():
        if is_valid_hermes_manifest(hermes_manifest):
            emit("PASS", f"manifest {HERMES_MANIFEST} valid (required keys present)")
            mn = (load_yaml_keys(hermes_manifest) or {}).get("name", "")
            if mn and mn != name:
                emit("FAIL", f"hermes manifest name='{mn}' != '{name}'")
        else:
            emit("FAIL", f"manifest {HERMES_MANIFEST} invalid — missing one of {HERMES_REQUIRED}")
    # required fields
    claude_manifest_path = path / ".claude-plugin" / "plugin.json"
    if claude_manifest_path.is_file():
        d = load_json(claude_manifest_path) or {}
        for k in REQUIRED_FIELDS:
            if not d.get(k):
                emit("FAIL", f".claude-plugin/plugin.json missing '{k}'")

    # 2. host-discovery dir symlinks — each host folder is ONE symlink to the
    #    root source of truth, so a skill added under skills/ shows up everywhere
    #    and can never drift into a per-host copy. Real directories here are the
    #    duplication bug: --fix replaces them with the symlink.
    def check_dirlink(rel: str, want: str):
        p = path / rel
        if p.is_symlink():
            got = os.readlink(p)
            if got == want:
                emit("PASS", f"{rel} -> {want} (dir symlink)")
                return
            reason = f"symlink points at {got!r}"
        elif p.exists():
            n = sum(1 for _ in p.rglob("*"))
            reason = f"real directory with {n} duplicated file(s)"
        else:
            reason = "missing"
        emit("WARN", f"{rel} should be a dir symlink -> {want} ({reason})")
        if fix:
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            p.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(want, p)
            emit("PASS", f"{rel} -> {want} linked (--fix)")

    if (path / "skills").is_dir() and any((path / "skills").glob("*/SKILL.md")):
        # a host is "selected" when either its discovery dir or its manifest
        # exists — a plugin.json/hermes plugin with no .hermes/skills link is
        # just as broken as a copied one.
        host_markers = {".claude": ".claude-plugin", ".codex": ".codex-plugin",
                        ".hermes": HERMES_MANIFEST}
        for host, marker in host_markers.items():
            if (path / host).is_dir() or (path / marker).exists():
                check_dirlink(f"{host}/skills", "../skills")
    else:
        emit("FAIL", "skills/*/SKILL.md (source of truth) missing")

    # 2b. agent discovery + codex-native TOML coverage.
    # Claude agents: root agents/*.md is the truth; .claude/agents links the
    # WHOLE folder (nested trees included, no flattening needed on a dir link).
    # Codex agents: NOT a symlink of the markdown — each agent is rewritten in
    # Codex-native TOML (name / description / developer_instructions) under
    # .codex-plugin/agents/, and .codex/agents links that folder.
    root_agents_dir = path / "agents"
    if root_agents_dir.is_dir():
        check_dirlink(".claude/agents", "../agents")
        codex_agents_dir = path / ".codex-plugin" / "agents"
        if codex_agents_dir.is_dir():
            check_dirlink(".codex/agents", "../.codex-plugin/agents")
            # coverage both ways: every md needs a toml twin; orphan tomls
            # mean the md was deleted or renamed.
            def _flat_stem(rel: str) -> str:
                s = rel[:-3] if rel.endswith(".md") else rel
                return s.replace("/", "__")
            md_stems = {_flat_stem(p.relative_to(root_agents_dir).as_posix())
                        for p in root_agents_dir.rglob("*.md") if p.is_file()}
            toml_stems = {p.stem for p in codex_agents_dir.glob("*.toml") if p.is_file()}
            for s in sorted(md_stems - toml_stems):
                emit("WARN", f"codex agent TOML missing: .codex-plugin/agents/{s}.toml "
                             f"(rewrite the agents/ markdown in Codex-native TOML — no auto-fix)")
            for s in sorted(toml_stems - md_stems):
                emit("WARN", f"codex agent TOML orphan: .codex-plugin/agents/{s}.toml "
                             f"has no agents/ markdown twin")
            if md_stems and md_stems == toml_stems:
                emit("PASS", f"codex-native TOML agents cover all {len(md_stems)} agent(s)")

    # 2b-2. hermes install pre-scan — hermes' skills_guard flags ANY scanned
    #        file mentioning AGENTS.md / CLAUDE.md / .cursorrules / .clinerules
    #        (even a README link) as CRITICAL persistence; community source +
    #        dangerous then hard-blocks `hermes plugins install` with no
    #        --force escape. Surface that at doctor time, not install time.
    if (path / ".hermes").is_dir() or (path / HERMES_MANIFEST).is_file():
        guard = re.compile(r"AGENTS\.md|CLAUDE\.md|\.cursorrules|\.clinerules")
        hits = []
        for f in sorted(path.rglob("*")):
            if not f.is_file() or f.is_symlink():
                continue
            rel = f.relative_to(path).as_posix()
            if rel.startswith(".git/"):
                continue
            try:
                if guard.search(f.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(rel)
            except OSError:
                continue
        if hits:
            shown = ", ".join(hits[:5]) + (f" (+{len(hits) - 5} more)" if len(hits) > 5 else "")
            emit("WARN", "hermes install scanner will flag (CRITICAL persistence): "
                 f"{shown} — `hermes plugins install` may BLOCK with no --force "
                 "(escape: plugins.scan_on_install: false)")
        else:
            emit("PASS", "hermes install pre-scan clean (no AGENTS/CLAUDE rule mentions)")

    # 2c. MCP single-source wiring: root mcp_config.json is the truth AND the
    #     agy plugin spec name (agy auto-discovers it; hermes has no file-based
    #     MCP convention, register() only). Claude declares it in the manifest;
    #     codex points its manifest at the same file. Legacy 0.1.6-0.1.8 wiring
    #     used root .mcp.json + a codex mcp_config.json symlink; --fix migrates.
    mcp_file = path / "mcp_config.json"
    legacy = path / ".mcp.json"
    grok_selected = (path / ".grok-plugin").is_dir() or (path / GROK_PLUGIN_MANIFEST).is_file()
    if mcp_file.is_file() or legacy.is_file() or legacy.is_symlink():
        if mcp_file.is_file() and not is_valid_json(mcp_file):
            emit("FAIL", "mcp_config.json is not valid JSON")
        if grok_selected:
            # grok reads root .mcp.json natively — keep it as a file symlink to
            # the agy-named truth (mcp_config.json), never a second copy.
            if legacy.is_symlink() and os.readlink(legacy) == "mcp_config.json" and mcp_file.is_file():
                emit("PASS", "grok: .mcp.json -> mcp_config.json (file symlink)")
            elif mcp_file.is_file() and not legacy.exists():
                emit("WARN", "grok: .mcp.json missing — should be a file symlink -> mcp_config.json")
                if fix:
                    os.symlink("mcp_config.json", legacy)
                    emit("PASS", "grok: .mcp.json linked (--fix)")
            elif legacy.is_file() and not mcp_file.exists():
                if fix:
                    legacy.rename(mcp_file)
                    os.symlink("mcp_config.json", legacy)
                    emit("PASS", "grok: .mcp.json adopted as mcp_config.json + linked (--fix)")
                else:
                    emit("WARN", "grok: real .mcp.json with no mcp_config.json — run "
                                 "doctor --fix to adopt it as the truth and link back")
            else:
                emit("WARN", "grok: .mcp.json should be a file symlink -> mcp_config.json "
                             "(merge any drift into the truth file first)")
        # legacy migration (non-grok plugins): fold .mcp.json into the agy-named file
        elif legacy.is_file():
            if mcp_file.is_symlink() or not mcp_file.is_file():
                if fix:
                    if mcp_file.is_symlink():
                        mcp_file.unlink()
                    if not mcp_file.exists():
                        mcp_file.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
                    legacy.unlink()
                    emit("PASS", "legacy .mcp.json migrated to mcp_config.json (--fix)")
                else:
                    emit("WARN", "root .mcp.json is legacy wiring; run doctor --fix to "
                                 "migrate it to mcp_config.json (the agy spec name)")
            elif mcp_file.is_file():
                emit("WARN", "both .mcp.json and mcp_config.json exist; merge manually "
                             "and delete .mcp.json")
        if claude_manifest_path.is_file():
            d = load_json(claude_manifest_path) or {}
            if isinstance(d.get("mcpServers"), list) and "./mcp_config.json" in d["mcpServers"]:
                emit("PASS", "claude mcpServers declares ./mcp_config.json")
            else:
                emit("WARN", 'claude manifest should declare mcpServers ["./mcp_config.json"]')
                if fix:
                    d["mcpServers"] = ["./mcp_config.json"]
                    claude_manifest_path.write_text(
                        json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    emit("PASS", "claude mcpServers declared (--fix)")
        if codex.is_file():
            d = load_json(codex) or {}
            if d.get("mcpServers") == "./mcp_config.json":
                emit("PASS", "codex mcpServers -> ./mcp_config.json")
            else:
                emit("WARN", "codex manifest should declare mcpServers ./mcp_config.json")
                if fix:
                    d["mcpServers"] = "./mcp_config.json"
                    codex.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    emit("PASS", "codex mcpServers declared (--fix)")
        emit("INFO", "agy auto-discovers root mcp_config.json; grok reads the .mcp.json "
                     "symlink; hermes has no MCP file convention")

    # 2d. grok LSP config (optional, schema undocumented — JSON validity only)
    lsp = path / ".lsp.json"
    if lsp.is_file() or lsp.is_symlink():
        if load_json(lsp) is None:
            emit("FAIL", ".lsp.json is not valid JSON")
        elif grok_selected:
            emit("PASS", "grok: .lsp.json valid JSON (schema undocumented — keys unchecked)")
        else:
            emit("INFO", ".lsp.json present (grok LSP config; other hosts ignore it)")

    # 3. structure consistency (paths resolve relative to the PLUGIN ROOT — the
    #    directory that CONTAINS .claude-plugin/plugin.json, NOT .claude-plugin/
    #    itself). `skills`/`commands` point at dirs; `agents`/`mcpServers` point
    #    at FILES and MUST be an array of file paths. Claude Code rejects a bare
    #    directory string (e.g. "agents": "./agents/") at load time with
    #    "<field>: Invalid input", so a string here is flagged even though the
    #    path may resolve. A declared-but-missing path is a real breakage → FAIL.
    if claude_manifest_path.is_file():
        d = load_json(claude_manifest_path) or {}
        dir_fields = ("skills", "commands")
        file_fields = ("agents", "mcpServers")
        for dk in (*dir_fields, *file_fields):
            dp = d.get(dk)
            if not dp:
                continue  # optional field not declared → nothing to verify
            # agents/mcpServers must be ARRAYS of file paths; a bare string fails
            # plugin load regardless of whether the path resolves.
            if dk in file_fields and isinstance(dp, str):
                emit("WARN", f".claude-plugin {dk} is a string ({dp!r}); Claude Code requires an array of file paths — manifest will fail to load")
            paths = dp if isinstance(dp, list) else [dp]
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                emit("WARN", f".claude-plugin {dk} has unexpected type (expected array of str)")
                continue
            for raw in paths:
                clean = raw[2:] if raw.startswith("./") else raw
                target = path / clean
                if dk in dir_fields:
                    ok = target.is_dir()
                else:
                    ok = target.is_file()
                if ok:
                    emit("PASS", f".claude-plugin {dk} -> {clean} exists")
                else:
                    emit("FAIL", f".claude-plugin {dk} -> {clean} not found")

    # 3b. lifecycle hooks (per-host: different paths, schemas, and event names)
    if (path / AMBIGUOUS_HOOK_FILE).is_file():
        if grok_selected:
            # hooks/hooks.json is grok's SPEC location — fine on its own, but it
            # is still the claude/codex DEFAULT, so those manifests must declare
            # their own hooks path or they will silently grab grok's file.
            emit("WARN", f"{AMBIGUOUS_HOOK_FILE} is grok's hook file AND the claude/codex "
                         f"default — declare hooks explicitly in {HOOK_FILES['claude']} / "
                         f"{HOOK_FILES['codex']} manifests if those hosts ship hooks too")
        else:
            emit("FAIL", f"{AMBIGUOUS_HOOK_FILE} is the default for BOTH claude and codex — "
                         f"split into {HOOK_FILES['claude']} / {HOOK_FILES['codex']}")

    for host, manifest_rel in ((("claude"), ".claude-plugin/plugin.json"),
                               (("codex"), ".codex-plugin/plugin.json")):
        mp = path / manifest_rel
        if not mp.is_file():
            continue
        declared = (load_json(mp) or {}).get("hooks")
        if not isinstance(declared, str):
            continue                      # absent or inline object -> nothing to resolve
        # NB: lstrip("./") would also eat the leading dot of ".claude-plugin"
        rel = declared[2:] if declared.startswith("./") else declared
        target = (path / rel).resolve()
        if not target.is_file():
            emit("FAIL", f"{host}: hooks path {declared!r} does not exist")
            continue
        # manifest paths resolve from the plugin ROOT, so a bare "hooks.json"
        # silently lands on the agy file
        if target == (path / HOOK_FILES["agy"]).resolve() and host != "agy":
            emit("FAIL", f"{host}: hooks path {declared!r} resolves to the agy hook file "
                         f"(root {HOOK_FILES['agy']}) — wrong schema and events")
            continue
        if (grok_selected and target == (path / HOOK_FILES["grok"]).resolve()
                and host in ("claude", "codex")):
            emit("FAIL", f"{host}: hooks path {declared!r} resolves to grok's hook file "
                         f"({HOOK_FILES['grok']}) — grok's hook schema is undocumented, "
                         f"do not share it across hosts")
            continue
        emit("PASS", f"{host}: hooks -> {declared} exists")

    for host, rel in HOOK_FILES.items():
        hp = path / rel
        if not hp.is_file():
            continue
        if host == "grok":
            # xAI documents hooks/hooks.json but not its event schema —
            # validate JSON only, never guess event names.
            if not grok_selected:
                continue
            if load_json(hp) is None:
                emit("FAIL", f"grok: {rel} is not valid JSON")
            else:
                emit("PASS", f"grok: {rel} valid JSON (event schema undocumented — names unchecked)")
            continue
        d = load_json(hp)
        if d is None:
            emit("FAIL", f"{host}: {rel} is not valid JSON")
            continue
        # claude/codex: {"hooks": {...}} — agy: {"<group>": {...}}
        if host == "agy":
            groups = [v for v in d.values() if isinstance(v, dict)]
            if not groups:
                emit("FAIL", f"agy: {rel} must wrap events in a named hook group")
                continue
            events = {k for g in groups for k in g if k != "enabled"}
        else:
            if not isinstance(d.get("hooks"), dict):
                emit("FAIL", f"{host}: {rel} must have a top-level 'hooks' object")
                continue
            events = set(d["hooks"].keys())
        unknown = events - HOST_HOOK_EVENTS[host]
        if unknown:
            emit("FAIL", f"{host}: unsupported event(s) {sorted(unknown)} in {rel}")
        else:
            emit("PASS", f"{host}: hook events valid ({len(events)})")

    init_py = path / "__init__.py"
    if init_py.is_file():
        try:
            text = init_py.read_text(encoding="utf-8")
        except Exception:
            text = ""
        if "register_hook" in text:
            names = set(_HOOK_LITERAL_RE.findall(text))
            unknown = names - HERMES_HOOK_EVENTS
            if unknown:
                emit("WARN", f"hermes: hook-shaped name(s) {sorted(unknown)} in __init__.py "
                             f"are not in hermes VALID_HOOKS — hermes only logs a warning, "
                             f"so a typo silently never fires")
            elif names:
                emit("PASS", f"hermes: register_hook names valid ({len(names)})")
            else:
                emit("INFO", "hermes: register_hook used with non-literal names — "
                             "cannot verify statically")

    # 3c. commands/ must stay THIN delegates to the SKILL. A command that
    #     restates the skill's arguments/checklists/host lists is the drift bug:
    #     every host added then needs N+1 edits and one of them gets missed.
    #     Heuristic: body (post-frontmatter) length + a reference to the skill.
    cmd_dir = path / "commands"
    if cmd_dir.is_dir():
        fat: list[str] = []
        no_ref: list[str] = []
        for cf in sorted(cmd_dir.glob("*.md")):
            # README.md documents the thin-delegate rule; it is not a command
            if cf.name.lower() == "readme.md":
                continue
            try:
                text = cf.read_text(encoding="utf-8")
            except OSError:
                continue
            # strip YAML frontmatter (--- ... ---) to measure only the body
            body = text
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) == 3:
                    body = parts[2]
            lines = [ln for ln in body.splitlines() if ln.strip()]
            rel = cf.relative_to(path).as_posix()
            if len(lines) > COMMAND_BODY_MAX_LINES:
                fat.append(f"{rel} ({len(lines)} lines)")
            elif "skill" not in body.lower():
                no_ref.append(rel)
        for f in fat:
            emit("WARN", f"command {f} exceeds {COMMAND_BODY_MAX_LINES} body lines — "
                         f"commands must be THIN delegates to the skill; move the "
                         f"arguments docs / checklists / host lists into skills/*/SKILL.md")
        for f in no_ref:
            emit("WARN", f"command {f} never mentions the skill — a slash command should "
                         f"delegate to skills/*/SKILL.md, not carry its own instructions")
        n = sum(1 for f in cmd_dir.glob("*.md") if f.name.lower() != "readme.md")
        if n and not fat and not no_ref:
            emit("PASS", f"commands are thin skill delegates ({n} file(s))")

    # 4. install dry-run (local structure)
    if (path / "plugin.json").is_file():
        emit("PASS", "agy: root plugin.json discoverable")
    else:
        emit("WARN", "agy: no root plugin.json (host may be skipped)")
    # bare mcp.json is the improvised name sessions reach for; no host reads it
    # (claude wants the manifest mcpServers path, codex/agy want mcp_config.json)
    if (path / "mcp.json").is_file():
        emit("FAIL", "root mcp.json found: no host reads it; rename to mcp_config.json")
    if (path / ".claude-plugin" / "marketplace.json").is_file():
        emit("PASS", "claude: marketplace.json present (marketplace add works)")
    else:
        emit("WARN", "claude: no marketplace.json (host may be skipped)")
    if codex.is_file():
        emit("PASS", "codex: manifest present")
    else:
        emit("WARN", "codex: no .codex-plugin/plugin.json (host may be skipped)")
    if (path / MARKETPLACE_MANIFESTS["codex"]).is_file():
        emit("PASS", "codex: .agents/plugins/marketplace.json present (marketplace add works)")
    if (path / HERMES_MANIFEST).is_file():
        emit("PASS", "hermes: root plugin.yaml discoverable")
    else:
        emit("WARN", "hermes: no root plugin.yaml (host may be skipped)")
    if (path / GROK_PLUGIN_MANIFEST).is_file():
        emit("PASS", "grok: .grok-plugin/plugin.json present (components read from root)")
    else:
        emit("WARN", "grok: no .grok-plugin/plugin.json (host may be skipped)")
    emit("INFO", "install dry-run = local structure check only (no host CLI invoked)")

    # 5. remote sync — owner/hub are the user's, never a forge default.
    if gh_available():
        owner = resolve_owner(args) or owner_from_git(path)
        if owner:
            if gh_ok("api", f"repos/{owner}/{name}"):
                emit("PASS", f"remote repo {owner}/{name} exists")
                meta = gh_json("api", f"repos/{owner}/{name}", "--jq", ".private")
                if meta is True or meta == "true":
                    emit("WARN", "remote repo is private (marketplace install needs public)")
            else:
                emit("WARN", f"remote repo {owner}/{name} not found (run: forge.py publish --owner {owner})")
        else:
            emit("INFO", "no --owner / PLUGIN_FORGE_OWNER / git origin; skip remote-repo check")
        hub = resolve_hub(args)
        if hub:
            content = gh_json("api", f"repos/{hub}/contents/.claude-plugin/marketplace.json", "--jq", ".content")
            if content:
                import base64
                try:
                    txt = base64.b64decode(content).decode("utf-8")
                    m = json.loads(txt)
                    if any(p.get("name") == name for p in m.get("plugins", [])):
                        emit("PASS", f"registered in hub {hub}")
                    else:
                        emit("WARN", f"not registered in hub {hub} (run: forge.py publish --marketplace {hub})")
                except Exception:
                    emit("WARN", f"cannot parse hub {hub}")
            else:
                emit("WARN", f"hub {hub} unreadable")
        else:
            emit("INFO", "no --marketplace / PLUGIN_FORGE_MARKETPLACE; skip hub registration check")
    else:
        emit("WARN", "gh not installed — remote sync checks skipped")

    print(f"\nSummary: {counts['PASS']} PASS, {counts['WARN']} WARN, {counts['FAIL']} FAIL")
    return 1 if counts["FAIL"] else 0


# ============================================================ install =======
def cmd_install(args) -> int:
    path = Path(args.path)
    if not path.is_dir():
        die(f"path not found: {path}")
    name = ""
    for rel in (".claude-plugin/plugin.json", "plugin.json", ".codex-plugin/plugin.json",
                GROK_PLUGIN_MANIFEST, HERMES_MANIFEST):
        if rel == HERMES_MANIFEST:
            d = load_yaml_keys(path / rel)
        else:
            d = load_json(path / rel)
        if d and d.get("name"):
            name = d["name"]
            break
    if not name:
        die("cannot determine plugin name")
    host = args.host
    print(f"🔧 install validation (dry-run) — {name}, host={host}")

    def val_claude():
        dest = Path.home() / ".claude" / "plugins" / f"forge-validate-{name}"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        # copy contents
        for item in path.iterdir():
            if item.name.startswith(".git"):
                continue
            if item.is_dir():
                shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest / item.name)
        ok = (dest / ".claude-plugin" / "marketplace.json").is_file()
        print(f"  claude: {'marketplace.json loadable -> OK' if ok else 'FAIL (no marketplace.json)'}")
        if not args.keep:
            shutil.rmtree(dest, ignore_errors=True)
        return ok

    def val_codex():
        ok_m = (path / ".codex-plugin" / "plugin.json").is_file()
        ok_c = (path / MARKETPLACE_MANIFESTS["codex"]).is_file()
        if ok_m and ok_c:
            msg = "manifest + .agents/plugins/marketplace.json -> OK"
        elif ok_m:
            msg = "FAIL (manifest ok but no .agents/plugins/marketplace.json)"
        else:
            msg = "FAIL (no .codex-plugin/plugin.json)"
        print(f"  codex: {msg}")
        return ok_m and ok_c

    def val_agy():
        f = path / "plugin.json"
        ok = f.is_file() and is_valid_json(f)
        print(f"  agy: {'root plugin.json valid -> OK' if ok else 'FAIL (no/invalid root plugin.json)'}")
        return ok

    def val_grok():
        f = path / GROK_PLUGIN_MANIFEST
        ok = f.is_file() and is_valid_json(f)
        print(f"  grok: {'.grok-plugin/plugin.json valid -> OK' if ok else 'FAIL (no/invalid .grok-plugin/plugin.json)'}")
        return ok

    def val_hermes():
        # hermes loads ~/.hermes/plugins/<name>/ with plugin.yaml + __init__.py
        dest = Path.home() / ".hermes" / "plugins" / f"forge-validate-{name}"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for item in path.iterdir():
            if item.name.startswith(".git"):
                continue
            if item.is_dir():
                shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest / item.name)
        ok_yaml = (dest / HERMES_MANIFEST).is_file() and is_valid_hermes_manifest(dest / HERMES_MANIFEST)
        ok_init = (dest / "__init__.py").is_file()
        if ok_yaml and ok_init:
            msg = "plugin.yaml + __init__.py present -> OK"
        elif ok_yaml and not ok_init:
            msg = "FAIL (plugin.yaml ok but no __init__.py with register(ctx))"
        else:
            msg = f"FAIL (no/invalid {HERMES_MANIFEST})"
        print(f"  hermes: {msg}")
        if not args.keep:
            shutil.rmtree(dest, ignore_errors=True)
        return ok_yaml and ok_init

    rc = 0
    for h in (VALID_HOSTS if host == "all" else [host]):
        if h == "claude" and not val_claude():
            rc = 1
        elif h == "codex" and not val_codex():
            rc = 1
        elif h == "agy" and not val_agy():
            rc = 1
        elif h == "hermes" and not val_hermes():
            rc = 1
        elif h == "grok" and not val_grok():
            rc = 1
        elif h not in VALID_HOSTS:
            die(f"unknown host: {h}")
    print("\n✓ install structure valid (dry-run — actual host load not verified)" if rc == 0 else "\n✗ validation failed")
    print("NOTE: this validates local structure discoverability only. Real install requires the host CLI.")
    return rc


# ============================================================ publish =======
def cmd_publish(args) -> int:
    path = Path(args.path).resolve()
    if not path.is_dir():
        die(f"path not found: {path}")
    name = ""
    for rel in (".claude-plugin/plugin.json", "plugin.json", ".codex-plugin/plugin.json",
                GROK_PLUGIN_MANIFEST, HERMES_MANIFEST):
        if rel == HERMES_MANIFEST:
            d = load_yaml_keys(path / rel)
        else:
            d = load_json(path / rel)
        if d and d.get("name"):
            name = d["name"]
            break
    if not name:
        die("cannot determine plugin name")
    if not gh_available():
        die("gh CLI required for publish")
    owner = resolve_owner(args) or owner_from_git(path)
    if not owner or owner == OWNER_PLACEHOLDER:
        die("publish needs a GitHub owner: --owner LOGIN or PLUGIN_FORGE_OWNER "
            "(no default; will not use another author's org)")
    want_hub = args.marketplace is not None
    hub = resolve_hub(args)
    if want_hub and not hub:
        die("publish --marketplace needs a hub repo: pass --marketplace OWNER/REPO "
            "or set PLUGIN_FORGE_MARKETPLACE (no default hub)")

    print(f"🚀 publish — {name}")
    if not (path / ".git").is_dir():
        run(["git", "init", "-b", "main"], cwd=path)
        print("  git initialized")
    run(["git", "add", "-A"], cwd=path)
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=path)
    if diff.returncode != 0:
        run(["git", "commit", "-q", "-m", f"chore: initial plugin ({name})"], cwd=path)
        print("  committed")

    repo = f"{owner}/{name}"
    if gh_ok("api", f"repos/{repo}"):
        print(f"  remote {repo} exists")
    elif args.no_push:
        print(f"  [dry-run] would: gh repo create {repo} --public --source . --push")
    else:
        r = run(["gh", "repo", "create", repo, "--public", "--source", ".", "--push"], cwd=path)
        if r.returncode == 0:
            print(f"  created {repo}")
        else:
            die("gh repo create failed")

    if not args.no_push:
        if run(["git", "remote", "get-url", "origin"], cwd=path).returncode == 0:
            run(["git", "push", "-u", "origin", "main"], cwd=path)

    ver = "0.1.0"
    d = load_json(path / ".claude-plugin" / "plugin.json")
    if not (d and d.get("version")):
        # fall back to hermes YAML / grok JSON manifests if claude manifest absent
        d = load_yaml_keys(path / HERMES_MANIFEST) or load_json(path / GROK_PLUGIN_MANIFEST)
    if d and d.get("version"):
        ver = d["version"]
    if args.no_push:
        print(f"  [dry-run] would tag v{ver}")
    else:
        run(["git", "tag", f"v{ver}"], cwd=path)
        run(["git", "push", "origin", f"v{ver}"], cwd=path)
        print(f"  tagged v{ver}")

    # grok catalog entries pin the exact commit — capture the pushed HEAD sha
    # (an unpushed sha would be unreachable, so dry-runs skip grok pinning).
    sha = None
    if not args.no_push:
        r = run(["git", "rev-parse", "HEAD"], cwd=path,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if r.returncode == 0:
            sha = r.stdout.strip()

    if want_hub:
        print(f"  registering in hub {hub} ...")
        import tempfile
        desc = (load_json(path / ".claude-plugin" / "plugin.json") or {}).get("description", name)
        ver = (load_json(path / ".claude-plugin" / "plugin.json") or {}).get("version", INITIAL_VERSION)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            if run(["gh", "repo", "clone", hub, str(td / "mpl")]).returncode == 0:
                mpl = td / "mpl"
                changed = register_marketplace(mpl, name, repo, desc, ver, sha=sha,
                                               owner=owner, hub=hub, plugin=path)
                missing = [c for c in changed if c.endswith(":MISSING")]
                needs_sha = [c for c in changed if c.endswith(":NEEDS_SHA")]
                skipped = [c for c in changed if c.endswith(":SKIP")]
                changed = [c for c in changed
                           if not any(c.endswith(s) for s in
                                      (":MISSING", ":NEEDS_SHA", ":SKIP"))]
                for m in missing:
                    host = m.split(":")[0]
                    print(f"  WARN: {MARKETPLACE_MANIFESTS[host]} not found in "
                          f"{hub} — {host} users will not see this plugin there")
                for m in skipped:
                    print(f"  WARN: {m.split(':')[0]} registration skipped — plugin "
                          f"has no hermes manifest ({HERMES_MANIFEST}); hermes "
                          f"install would fail on this repo")
                for m in needs_sha:
                    host = m.split(":")[0]
                    print(f"  WARN: {host} registration skipped — catalog entries need the "
                          f"pushed commit sha; re-run publish --marketplace after a real push")
                if changed:
                    run(["git", "add", "-A"], cwd=mpl)
                    run(["git", "commit", "-q", "-m",
                         f"feat(marketplace): {name} ({', '.join(changed)})"], cwd=mpl)
                    if not args.no_push:
                        run(["git", "push"], cwd=mpl)
                    print(f"  hub updated: {', '.join(changed)}")
                else:
                    print("  hub: already registered for all hosts")
            else:
                print(f"  WARN: cannot clone {hub} — register manually")

    print(f"\nInstall:\n  claude plugin marketplace add {owner}/{name} && claude plugin install {name}@{name}")
    print(f"  codex plugin marketplace add {owner}/{name} && codex plugin add {name}@{name}")
    print(f"  agy plugin install https://github.com/{owner}/{name} && agy plugin enable {name}")
    print(f"  hermes plugins install https://github.com/{owner}/{name} && hermes plugins enable {name}")
    print(f"  grok plugin install {owner}/{name} --trust")
    return 0


# ============================================================ main ==========
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="forge.py", description="Multi-host plugin manager")
    p.add_argument("--version", action="version", version=f"forge.py {VERSION}")
    sub = p.add_subparsers(dest="cmd")

    pc = sub.add_parser("create", help="scaffold a new plugin")
    pc.add_argument("name")
    pc.add_argument("--owner", default="",
                    help="GitHub user or org (or PLUGIN_FORGE_OWNER). Empty writes YOUR_GITHUB_USER")
    pc.add_argument("--hosts", default="claude,codex,agy,hermes,grok")
    pc.add_argument("--desc", default="A plugin.")
    pc.add_argument("--display-name")
    pc.add_argument("--dir")
    pc.add_argument("--mcp", action="store_true",
                    help="scaffold root mcp_config.json (agy spec name) + manifest wiring")
    pc.set_defaults(func=cmd_create)

    pd = sub.add_parser("doctor", help="validate plugin structure")
    pd.add_argument("path", nargs="?", default=".")
    pd.add_argument("--fix", action="store_true")
    pd.add_argument("--owner", default="",
                    help="GitHub user or org for remote-repo check (or PLUGIN_FORGE_OWNER / git origin)")
    pd.add_argument("--marketplace", default="", metavar="OWNER/REPO",
                    help="optional hub catalog to check (or PLUGIN_FORGE_MARKETPLACE). No default")
    pd.set_defaults(func=cmd_doctor)

    pi = sub.add_parser("install", help="validate local installability")
    pi.add_argument("path")
    pi.add_argument("--host", default="all")
    pi.add_argument("--keep", action="store_true")
    pi.set_defaults(func=cmd_install)

    pp = sub.add_parser("publish", help="ship to GitHub; optionally register in a hub catalog")
    pp.add_argument("path", nargs="?", default=".")
    pp.add_argument("--owner", default="",
                    help="GitHub user or org (or PLUGIN_FORGE_OWNER). Required; no default")
    pp.add_argument("--marketplace", nargs="?", const="", default=None, metavar="OWNER/REPO",
                    help="also register in a hub catalog. Pass OWNER/REPO or set "
                         "PLUGIN_FORGE_MARKETPLACE. No default hub")
    pp.add_argument("--no-push", action="store_true")
    pp.set_defaults(func=cmd_publish)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
