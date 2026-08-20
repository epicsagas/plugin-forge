#!/usr/bin/env python3
"""forge.py — multi-host plugin manager (create / doctor / install / publish).

Cross-platform (Windows / Linux / macOS). Standard library only.
Hosts: claude (Claude Code), codex (Codex), agy (Antigravity CLI),
       hermes (Nous Research Hermes Agent).

Manifest pattern (toefl-prep / byoh):
  plugin.json (root)               -> agy
  plugin.yaml (root)               -> hermes (YAML manifest)
  .claude-plugin/plugin.json       -> Claude Code (skills/commands/agents)
  .claude-plugin/marketplace.json  -> Claude marketplace (source "./")
  .codex-plugin/plugin.json        -> Codex (interface block)
  .claude/skills, .codex/skills, .hermes/skills -> dir symlinks to ../skills
  .claude/agents -> ../agents (dir symlink); codex agents are NATIVE TOML
  under .codex-plugin/agents/<n>.toml, linked from .codex/agents

Usage:
  python3 forge.py create   <name> [--hosts claude,codex,agy,hermes] [--desc "..."] [--dir PATH]
  python3 forge.py doctor   [PATH] [--fix]
  python3 forge.py install  <PATH>  [--host claude|codex|agy|hermes|all] [--keep]
  python3 forge.py publish  [PATH]  [--marketplace] [--no-push]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, textwrap
from pathlib import Path

VERSION = "0.1.8"
# Version stamped into a NEWLY created plugin. Kept separate from VERSION so
# forge's own version never leaks into generated manifests.
INITIAL_VERSION = "0.1.0"
SCRIPT_DIR = Path(__file__).resolve().parent
TPL_DIR = SCRIPT_DIR / "templates"
OWNER = os.environ.get("PLUGIN_FORGE_OWNER", "epicsagas")
MARKETPLACE_REPO = os.environ.get("PLUGIN_FORGE_MARKETPLACE", f"{OWNER}/plugins")

# Each host reads a DIFFERENT marketplace manifest. Registering only the Claude
# one leaves the plugin invisible to `codex plugin add` with no error at
# publish time, so all three are kept in sync.
MARKETPLACE_MANIFESTS = {
    "claude": ".claude-plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
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

VALID_HOSTS = ("claude", "codex", "agy", "hermes")
MANIFEST_SCHEMAS = {
    "plugin.json": "https://antigravity.google/schemas/v1/plugin.json",
    ".claude-plugin/plugin.json": "https://json.schemastore.org/claude-code-plugin-manifest.json",
    ".claude-plugin/marketplace.json": "https://anthropic.com/claude-code/marketplace.schema.json",
}
REQUIRED_FIELDS = ("name", "version", "description")
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


def register_marketplace(mpl: Path, name: str, repo: str, desc: str, version: str) -> list[str]:
    """Register the plugin in every host's marketplace manifest.

    Claude reads .claude-plugin/marketplace.json, Codex reads
    .agents/plugins/marketplace.json, and hermes reads one plugin.yaml per
    plugin. Registering only Claude's leaves `codex plugin add` failing with
    "not found in marketplace" even though publish reported success.
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

    # --- hermes (one plugin.yaml per plugin) ---
    hf = mpl / MARKETPLACE_MANIFESTS["hermes"].format(name=name)
    if (mpl / ".hermes").is_dir():
        if not hf.is_file():
            hf.parent.mkdir(parents=True, exist_ok=True)
            hf.write_text(
                f'name: {name}\nversion: "{version}"\ndescription: {desc}\n'
                f'provides_skills:\n  - {name}\n', encoding="utf-8")
            changed.append("hermes")
        else:
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
    target = Path(args.dir).expanduser() / name if args.dir else Path.cwd() / name
    target.mkdir(parents=True, exist_ok=True)
    print(f"🔨 Creating plugin '{name}' (hosts: {','.join(hosts)}) -> {target}")

    ctx = dict(NAME=name, DESC=args.desc, DISPLAYNAME=disp, OWNER=OWNER, VERSION=INITIAL_VERSION)

    # source of truth skill
    skill_dir = target / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (target / "commands").mkdir(exist_ok=True)
    (target / "commands" / ".gitkeep").touch()
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

    # MCP single source of truth: root .mcp.json. Codex convention names the
    # config mcp_config.json, so it gets a FILE symlink to .mcp.json — never a
    # copy. Claude declares the root file directly; agy auto-discovers it.
    if args.mcp:
        (target / ".mcp.json").write_text(json.dumps(
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
            d["mcpServers"] = ["./.mcp.json"]
            mf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "codex" in hosts:
        render(TPL_DIR / "plugin.json.codex.tpl", target / ".codex-plugin" / "plugin.json", **ctx)
        ensure_dirlink(target / ".codex" / "skills", "../skills")
        if args.mcp:
            mf = target / ".codex-plugin" / "plugin.json"
            d = load_json(mf) or {}
            d["mcpServers"] = "./mcp_config.json"
            mf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            ensure_dirlink(target / "mcp_config.json", ".mcp.json")
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

        > Shared agent guide. Claude Code, Codex, agy, and hermes all load this file.

        ## Role

        TODO: describe what this plugin does. The authoritative workflow is
        `skills/{name}/SKILL.md`; host-discovery dirs (`.claude/skills`,
        `.codex/skills`, `.hermes/skills`) are symlinks to the root `skills/`.
        Agents live in root `agents/*.md` (Claude) and are converted to
        Codex-native TOML under `.codex-plugin/agents/`.

        ## Host differences

        - **Claude Code**: uses `commands/` (slash commands) + SKILL.
        - **Codex / agy / hermes**: no `commands/` support — follow SKILL.md intent->action table.
    """), encoding="utf-8")

    (target / "README.md").write_text(textwrap.dedent(f"""\
        # {name}

        > TODO: replace this stub README. Multi-host plugin (Claude Code · Codex · agy · hermes).

        ## Install

        ```bash
        # Claude Code
        claude plugin marketplace add {MARKETPLACE_REPO}
        claude plugin install {name}@{OWNER}

        # Codex
        codex plugin marketplace add {MARKETPLACE_REPO}
        codex plugin add {name}@{OWNER}

        # agy (repo URL, no .git)
        agy plugin install https://github.com/{OWNER}/{name}
        agy plugin enable {name}

        # hermes (repo URL)
        hermes plugins install https://github.com/{OWNER}/{name}
        hermes plugins enable {name}
        # Blocked by skills_guard (AGENTS.md mention → CRITICAL persistence)?
        # Disable the install scan in hermes config: plugins.scan_on_install: false
        ```

        ## License

        MIT
    """), encoding="utf-8")

    (target / "LICENSE").write_text(textwrap.dedent(f"""\
        MIT License

        Copyright (c) 2026 {OWNER}

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
    print(f"\nNext: edit skills/{name}/SKILL.md, then:\n  forge.py doctor {target}\n  forge.py publish {target} --marketplace")
    return 0


# ============================================================ doctor ========
def cmd_doctor(args) -> int:
    path = Path(args.path)
    if not path.is_dir():
        die(f"path not found: {path}")
    # infer name
    name = ""
    for rel in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json", HERMES_MANIFEST):
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

    # 2c. MCP single-source wiring — root .mcp.json is the truth; codex's
    #     mcp_config.json must be a FILE symlink to it (convention from
    #     BYOH/gamestudio: same {"mcpServers": {...}} shape, different name),
    #     claude's manifest must declare the root file. agy auto-discovers the
    #     root file; hermes has no file-based MCP convention (register() only).
    mcp_file = path / ".mcp.json"
    if mcp_file.is_file():
        if claude_manifest_path.is_file():
            d = load_json(claude_manifest_path) or {}
            if isinstance(d.get("mcpServers"), list) and "./.mcp.json" in d["mcpServers"]:
                emit("PASS", "claude mcpServers declares ./.mcp.json")
            else:
                emit("WARN", 'claude manifest should declare mcpServers ["./.mcp.json"]')
                if fix:
                    d["mcpServers"] = ["./.mcp.json"]
                    claude_manifest_path.write_text(
                        json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    emit("PASS", "claude mcpServers declared (--fix)")
        if codex.is_file():
            d = load_json(codex) or {}
            link = path / "mcp_config.json"
            link_ok = link.is_symlink() and os.readlink(link) == ".mcp.json"
            if d.get("mcpServers") == "./mcp_config.json" and link_ok:
                emit("PASS", "codex mcpServers -> mcp_config.json -> .mcp.json (symlink)")
            else:
                why = []
                if d.get("mcpServers") != "./mcp_config.json":
                    why.append("manifest not pointing at ./mcp_config.json")
                if not link_ok:
                    why.append("mcp_config.json not a symlink to .mcp.json")
                emit("WARN", f"codex MCP wiring incomplete ({'; '.join(why)})")
                if fix:
                    if d.get("mcpServers") != "./mcp_config.json":
                        d["mcpServers"] = "./mcp_config.json"
                        codex.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    if not link_ok:
                        ensure_dirlink(link, ".mcp.json")
                    emit("PASS", "codex MCP wired via symlink (--fix)")
        emit("INFO", "agy auto-discovers root .mcp.json; hermes has no MCP file convention")

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
        emit("PASS", f"{host}: hooks -> {declared} exists")

    for host, rel in HOOK_FILES.items():
        hp = path / rel
        if not hp.is_file():
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

    # 4. install dry-run (local structure)
    if (path / "plugin.json").is_file():
        emit("PASS", "agy: root plugin.json discoverable")
    else:
        emit("WARN", "agy: no root plugin.json (host may be skipped)")
    if (path / ".claude-plugin" / "marketplace.json").is_file():
        emit("PASS", "claude: marketplace.json present (marketplace add works)")
    else:
        emit("WARN", "claude: no marketplace.json (host may be skipped)")
    if codex.is_file():
        emit("PASS", "codex: manifest present")
    else:
        emit("WARN", "codex: no .codex-plugin/plugin.json (host may be skipped)")
    if (path / HERMES_MANIFEST).is_file():
        emit("PASS", "hermes: root plugin.yaml discoverable")
    else:
        emit("WARN", "hermes: no root plugin.yaml (host may be skipped)")
    emit("INFO", "install dry-run = local structure check only (no host CLI invoked)")

    # 5. remote sync
    if gh_available():
        if gh_ok("api", f"repos/{OWNER}/{name}"):
            emit("PASS", f"remote repo {OWNER}/{name} exists")
            meta = gh_json("api", f"repos/{OWNER}/{name}", "--jq", ".private")
            if meta is True or meta == "true":
                emit("WARN", "remote repo is private (marketplace install needs public)")
        else:
            emit("WARN", f"remote repo {OWNER}/{name} not found (run: forge.py publish)")
        # marketplace registration
        content = gh_json("api", f"repos/{MARKETPLACE_REPO}/contents/.claude-plugin/marketplace.json", "--jq", ".content")
        if content:
            import base64
            try:
                txt = base64.b64decode(content).decode("utf-8")
                m = json.loads(txt)
                if any(p.get("name") == name for p in m.get("plugins", [])):
                    emit("PASS", f"registered in marketplace {MARKETPLACE_REPO}")
                else:
                    emit("WARN", f"not registered in marketplace {MARKETPLACE_REPO} (run: forge.py publish --marketplace)")
            except Exception:
                emit("WARN", f"cannot parse marketplace {MARKETPLACE_REPO}")
        else:
            emit("WARN", f"marketplace {MARKETPLACE_REPO} unreadable")
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
    for rel in (".claude-plugin/plugin.json", "plugin.json", HERMES_MANIFEST):
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
        ok = (path / ".codex-plugin" / "plugin.json").is_file()
        print(f"  codex: {'manifest loadable -> OK' if ok else 'FAIL (no .codex-plugin/plugin.json)'}")
        return ok

    def val_agy():
        f = path / "plugin.json"
        ok = f.is_file() and is_valid_json(f)
        print(f"  agy: {'root plugin.json valid -> OK' if ok else 'FAIL (no/invalid root plugin.json)'}")
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
    for rel in (".claude-plugin/plugin.json", "plugin.json", HERMES_MANIFEST):
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

    print(f"🚀 publish — {name}")
    if not (path / ".git").is_dir():
        run(["git", "init", "-b", "main"], cwd=path)
        print("  git initialized")
    run(["git", "add", "-A"], cwd=path)
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=path)
    if diff.returncode != 0:
        run(["git", "commit", "-q", "-m", f"chore: initial plugin ({name})"], cwd=path)
        print("  committed")

    repo = f"{OWNER}/{name}"
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
        # fall back to hermes YAML manifest if claude manifest absent
        d = load_yaml_keys(path / HERMES_MANIFEST)
    if d and d.get("version"):
        ver = d["version"]
    if args.no_push:
        print(f"  [dry-run] would tag v{ver}")
    else:
        run(["git", "tag", f"v{ver}"], cwd=path)
        run(["git", "push", "origin", f"v{ver}"], cwd=path)
        print(f"  tagged v{ver}")

    if args.marketplace:
        print(f"  registering in marketplace {MARKETPLACE_REPO} ...")
        import tempfile
        desc = (load_json(path / ".claude-plugin" / "plugin.json") or {}).get("description", name)
        ver = (load_json(path / ".claude-plugin" / "plugin.json") or {}).get("version", INITIAL_VERSION)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            if run(["gh", "repo", "clone", MARKETPLACE_REPO, str(td / "mpl")]).returncode == 0:
                mpl = td / "mpl"
                changed = register_marketplace(mpl, name, repo, desc, ver)
                missing = [c for c in changed if c.endswith(":MISSING")]
                changed = [c for c in changed if not c.endswith(":MISSING")]
                for m in missing:
                    host = m.split(":")[0]
                    print(f"  WARN: {MARKETPLACE_MANIFESTS[host]} not found in "
                          f"{MARKETPLACE_REPO} — {host} users will not see this plugin")
                if changed:
                    run(["git", "add", "-A"], cwd=mpl)
                    run(["git", "commit", "-q", "-m",
                         f"feat(marketplace): {name} ({', '.join(changed)})"], cwd=mpl)
                    if not args.no_push:
                        run(["git", "push"], cwd=mpl)
                    print(f"  marketplace updated: {', '.join(changed)}")
                else:
                    print("  marketplace: already registered for all hosts")
            else:
                print(f"  WARN: cannot clone {MARKETPLACE_REPO} — register manually")

    print(f"\nInstall:\n  claude plugin marketplace add {MARKETPLACE_REPO} && claude plugin install {name}@{OWNER}")
    print(f"  codex plugin marketplace add {MARKETPLACE_REPO} && codex plugin add {name}@{OWNER}")
    print(f"  agy plugin install https://github.com/{OWNER}/{name} && agy plugin enable {name}")
    print(f"  hermes plugins install https://github.com/{OWNER}/{name} && hermes plugins enable {name}")
    return 0


# ============================================================ main ==========
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="forge.py", description="Multi-host plugin manager")
    p.add_argument("--version", action="version", version=f"forge.py {VERSION}")
    sub = p.add_subparsers(dest="cmd")

    pc = sub.add_parser("create", help="scaffold a new plugin")
    pc.add_argument("name")
    pc.add_argument("--hosts", default="claude,codex,agy,hermes")
    pc.add_argument("--desc", default="A plugin.")
    pc.add_argument("--display-name")
    pc.add_argument("--dir")
    pc.add_argument("--mcp", action="store_true",
                    help="scaffold root .mcp.json + per-host MCP wiring")
    pc.set_defaults(func=cmd_create)

    pd = sub.add_parser("doctor", help="validate plugin structure")
    pd.add_argument("path", nargs="?", default=".")
    pd.add_argument("--fix", action="store_true")
    pd.set_defaults(func=cmd_doctor)

    pi = sub.add_parser("install", help="validate local installability")
    pi.add_argument("path")
    pi.add_argument("--host", default="all")
    pi.add_argument("--keep", action="store_true")
    pi.set_defaults(func=cmd_install)

    pp = sub.add_parser("publish", help="ship to GitHub + marketplace")
    pp.add_argument("path", nargs="?", default=".")
    pp.add_argument("--marketplace", action="store_true")
    pp.add_argument("--no-push", action="store_true")
    pp.set_defaults(func=cmd_publish)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
