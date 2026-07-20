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
  .claude/skills/<n>/, .codex/skills/<n>/, .hermes/skills/<n>/ -> host-discovery SKILL copies

Usage:
  python3 forge.py create   <name> [--hosts claude,codex,agy,hermes] [--desc "..."] [--dir PATH]
  python3 forge.py doctor   [PATH] [--fix]
  python3 forge.py install  <PATH>  [--host claude|codex|agy|hermes|all] [--keep]
  python3 forge.py publish  [PATH]  [--marketplace] [--no-push]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, textwrap
from pathlib import Path

VERSION = "0.1.3"
SCRIPT_DIR = Path(__file__).resolve().parent
TPL_DIR = SCRIPT_DIR / "templates"
OWNER = os.environ.get("PLUGIN_FORGE_OWNER", "epicsagas")
MARKETPLACE_REPO = os.environ.get("PLUGIN_FORGE_MARKETPLACE", f"{OWNER}/plugins")

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


# ============================================================ create =========
def cmd_create(args) -> int:
    name = args.name
    if not name.replace("-", "").isalnum() or not name.islower() or name != name.lower():
        die("name must be lowercase-kebab (^[a-z0-9-]+$)")
    hosts = [h for h in (args.hosts.split(",") if args.hosts else []) if h] or list(VALID_HOSTS)
    for h in hosts:
        if h not in VALID_HOSTS:
            die(f"unknown host: {h} (claude|codex|agy)")
    disp = args.display_name or name
    target = Path(args.dir) if args.dir else Path.cwd() / name
    target.mkdir(parents=True, exist_ok=True)
    print(f"🔨 Creating plugin '{name}' (hosts: {','.join(hosts)}) -> {target}")

    ctx = dict(NAME=name, DESC=args.desc, DISPLAYNAME=disp, OWNER=OWNER, VERSION=VERSION)

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

        > TODO: describe the workflow. This SKILL.md is the authoritative source; the
        > host-discovery copies under .claude/skills/ and .codex/skills/ mirror it
        > (run `forge doctor` to keep them in sync).

        ## Intents -> actions

        | User intent | Action |
        |-------------|--------|
        | TODO | TODO |
    """), encoding="utf-8")

    if "agy" in hosts:
        render(TPL_DIR / "plugin.json.agy.tpl", target / "plugin.json", **ctx)
    if "claude" in hosts:
        render(TPL_DIR / "plugin.json.claude.tpl", target / ".claude-plugin" / "plugin.json", **ctx)
        render(TPL_DIR / "marketplace.json.tpl", target / ".claude-plugin" / "marketplace.json", **ctx)
        dc = target / ".claude" / "skills" / name
        dc.mkdir(parents=True, exist_ok=True)
        dst = dc / "SKILL.md"
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        os.symlink("../../../skills/" + name + "/SKILL.md", dst)
    if "codex" in hosts:
        render(TPL_DIR / "plugin.json.codex.tpl", target / ".codex-plugin" / "plugin.json", **ctx)
        dc = target / ".codex" / "skills" / name
        dc.mkdir(parents=True, exist_ok=True)
        dst = dc / "SKILL.md"
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        os.symlink("../../../skills/" + name + "/SKILL.md", dst)
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
        dc = target / ".hermes" / "skills" / name
        dc.mkdir(parents=True, exist_ok=True)
        dst = dc / "SKILL.md"
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        os.symlink("../../../skills/" + name + "/SKILL.md", dst)

    (target / "AGENTS.md").write_text(textwrap.dedent(f"""\
        # AGENTS.md — {name}

        > Shared agent guide. Claude Code, Codex, agy, and hermes all load this file.

        ## Role

        TODO: describe what this plugin does. The authoritative workflow is
        `skills/{name}/SKILL.md`. Host-discovery copies live under `.claude/skills/`,
        `.codex/skills/`, and `.hermes/skills/` and must mirror it.

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
        claude plugin install {OWNER}@{name}

        # Codex
        codex plugin marketplace add {MARKETPLACE_REPO}
        codex plugin add {OWNER}@{name}

        # agy (repo URL, no .git)
        agy plugin install https://github.com/{OWNER}/{name}
        agy plugin enable {name}

        # hermes (repo URL)
        hermes plugins install https://github.com/{OWNER}/{name}
        hermes plugins enable {name}
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

    # 2. host-discovery copy sync (symlinks)
    skill_dir = next((p for p in (path / "skills").glob("*/") if (p / "SKILL.md").is_file()), None) if (path / "skills").is_dir() else None
    if skill_dir and (skill_dir / "SKILL.md").is_file():
        sname = skill_dir.name
        for host in (".claude", ".codex", ".hermes"):
            discovery_path = path / host / "skills" / sname / "SKILL.md"
            want_target = "../../../skills/" + sname + "/SKILL.md"
            
            is_ok = False
            if discovery_path.is_symlink():
                got_target = os.readlink(discovery_path)
                if got_target == want_target:
                    is_ok = True
            
            if is_ok:
                emit("PASS", f"{host} discovery copy in sync (symlink)")
            else:
                emit("WARN", f"{host} discovery copy drifted or not a symlink")
                if fix:
                    discovery_path.parent.mkdir(parents=True, exist_ok=True)
                    if discovery_path.exists() or discovery_path.is_symlink():
                        discovery_path.unlink()
                    os.symlink(want_target, discovery_path)
                    emit("PASS", f"{host} symlink re-synced (--fix)")
    else:
        emit("FAIL", "skills/*/SKILL.md (source of truth) missing")

    # 2b. agent discovery sync (symlinks)
    # Claude agents: if root/agents exists, symlink to .claude/agents/
    root_agents_dir = path / "agents"
    if root_agents_dir.is_dir():
        claude_agents_dest = path / ".claude" / "agents"
        # rglob so nested agent trees (agents/directors/, agents/engines/<e>/,
        # agents/specialists/) are discovered, not just top-level files. A nested
        # rel path is flattened for the symlink NAME to avoid collisions across
        # subdirs (e.g. engines/godot/lead.md -> engines__godot__lead.md) while
        # the symlink target keeps the real relative path.
        for ag_file in root_agents_dir.rglob("*.md"):
            if ag_file.is_file():
                rel = ag_file.relative_to(root_agents_dir).as_posix()
                flat_name = rel.replace("/", "__") if "/" in rel else ag_file.name
                want_target = "../../agents/" + rel
                discovery_path = claude_agents_dest / flat_name

                is_ok = False
                if discovery_path.is_symlink():
                    if os.readlink(discovery_path) == want_target:
                        is_ok = True

                if is_ok:
                    emit("PASS", f"claude agent {rel} in sync (symlink)")
                else:
                    emit("WARN", f"claude agent {rel} drifted or not a symlink")
                    if fix:
                        claude_agents_dest.mkdir(parents=True, exist_ok=True)
                        if discovery_path.exists() or discovery_path.is_symlink():
                            discovery_path.unlink()
                        os.symlink(want_target, discovery_path)
                        emit("PASS", f"claude agent {rel} symlinked (--fix)")

    # Codex agents: if .codex-plugin/agents/ exists, symlink to .codex/agents/ (TOML files)
    codex_plugin_agents = path / ".codex-plugin" / "agents"
    if codex_plugin_agents.is_dir():
        codex_agents_dest = path / ".codex" / "agents"
        for ag_file in codex_plugin_agents.glob("*.toml"):
            if ag_file.is_file():
                want_target = "../../.codex-plugin/agents/" + ag_file.name
                discovery_path = codex_agents_dest / ag_file.name
                
                is_ok = False
                if discovery_path.is_symlink():
                    if os.readlink(discovery_path) == want_target:
                        is_ok = True
                
                if is_ok:
                    emit("PASS", f"codex agent {ag_file.name} in sync (symlink)")
                else:
                    emit("WARN", f"codex agent {ag_file.name} drifted or not a symlink")
                    if fix:
                        codex_agents_dest.mkdir(parents=True, exist_ok=True)
                        if discovery_path.exists() or discovery_path.is_symlink():
                            discovery_path.unlink()
                        os.symlink(want_target, discovery_path)
                        emit("PASS", f"codex agent {ag_file.name} symlinked (--fix)")

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
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            if run(["gh", "repo", "clone", MARKETPLACE_REPO, str(td / "mpl")]).returncode == 0:
                mf = td / "mpl" / ".claude-plugin" / "marketplace.json"
                m = load_json(mf) or {"plugins": []}
                if not any(p.get("name") == name for p in m.get("plugins", [])):
                    m.setdefault("plugins", []).append({
                        "name": name,
                        "source": {"source": "url", "url": f"https://github.com/{repo}.git"},
                        "description": name,
                    })
                    mf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    run(["git", "add", "-A"], cwd=td / "mpl")
                    run(["git", "commit", "-q", "-m", f"feat(marketplace): add {name}"], cwd=td / "mpl")
                    if not args.no_push:
                        run(["git", "push"], cwd=td / "mpl")
                    print("  marketplace updated")
                else:
                    print("  marketplace: already registered")
            else:
                print(f"  WARN: cannot clone {MARKETPLACE_REPO} — register manually")

    print(f"\nInstall:\n  claude plugin marketplace add {MARKETPLACE_REPO} && claude plugin install {OWNER}@{name}")
    print(f"  codex plugin marketplace add {MARKETPLACE_REPO} && codex plugin add {OWNER}@{name}")
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
