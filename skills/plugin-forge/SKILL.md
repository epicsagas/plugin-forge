---
name: plugin-forge
description: >
  Multi-host plugin manager (Claude Code, Codex, agy, hermes, grok). Use when the
  user asks to create a plugin, scaffold a plugin, check or doctor a plugin,
  validate a local install, publish a plugin, or register it in a marketplace
  (including Korean phrasings such as "플러그인 만들어", "플러그인 점검",
  "마켓 등록"). Scaffolds, checks, install-validates, and ships plugins using the
  manifest pattern established by toefl-prep and byoh: root plugin.json for agy,
  plugin.yaml for hermes, .claude-plugin for claude, .codex-plugin for codex,
  .grok-plugin for grok, plus directory symlinks for host discovery.
---

# plugin-forge, multi-host plugin manager

Scaffold a new plugin in the five-host layout (claude, codex, agy, hermes, grok), check its manifests, validate a local install, and ship it to GitHub and a marketplace.

> **Engine**: `${CLAUDE_PLUGIN_ROOT}/scripts/forge.py` is the single source of truth. Every host follows this skill and calls `forge.py` directly per the mapping below. This plugin ships no slash commands: the skill is the only interface, so there is no second spec to drift.

## Manifest pattern (toefl-prep baseline)

| File | Host |
|------|------|
| `plugin.json` (root) | agy |
| `plugin.yaml` (root) | hermes (YAML manifest plus `register(ctx)` in `__init__.py`) |
| `.claude-plugin/plugin.json` | Claude Code (skills/agents/mcpServers) |
| `.claude-plugin/marketplace.json` | Claude marketplace (source `"./"`) |
| `.codex-plugin/plugin.json` | Codex (interface block). This folder holds only plugin.json; the catalog is separate |
| `.agents/plugins/marketplace.json` | Codex standalone catalog. create writes a `./plugins/<name>` local source (Codex rejects a `"./"` root). `plugins/<name>/` holds dirlinks to the root `.codex-plugin`, `skills`, and so on |
| `.grok-plugin/plugin.json` | grok (xAI Grok Build) metadata manifest. Components (`skills/`, `agents/`) are read natively from the plugin root, so no discovery symlink is needed. Only flat path keys work (`"skills": "./skills/"`); a `components` object is ignored (measured on 1.0.13). Hooks load solely from root `hooks/hooks.json` (A/B deletion test), so the manifest hooks key is documentation only. Hook schema is Claude-compatible (same events and matcher) minus the `async` field, and `GROK_PLUGIN_ROOT` is injected. [xAI catalog reference](https://github.com/xai-org/plugin-marketplace) |
| `.grok-plugin/marketplace.json` | grok catalog. **create does not generate one** (there is no sha to pin before the first push). A standalone catalog is valid with a remote url+sha source: a standalone catalog pinning its own repo HEAD is listed by the browser (measured 1.0.13, plugin_count=1). A local `"."` self-reference is not listed (same version, 0), so doctor WARNs on it; a subdirectory local source is structurally validated only, which does not guarantee display |
| `.claude/skills`, `.codex/skills`, `.hermes/skills` | **Directory symlinks to `../skills`** for local discovery. Never copies: do not duplicate skills |
| `agents/*.md` (root) | Agent source of truth (Claude markdown format) |
| `.claude/agents` | **Directory symlink to `../agents`** |
| `.codex-plugin/agents/<n>.toml` | **Codex-native TOML conversion** (`name`, `description`, `developer_instructions`). `.codex/agents` symlinks to this folder. Never link the markdown directly |
| `mcp_config.json` (root) | **Single MCP source, agy spec filename** (Antigravity plugin spec). claude declares `mcpServers: ["./mcp_config.json"]` in its manifest, codex declares `mcpServers: "./mcp_config.json"`, agy auto-discovers it at the root (no wiring), grok gets a root `.mcp.json` **file symlink to `mcp_config.json`** (the name the grok spec reads), and hermes has no MCP file convention. Never create a root `mcp.json`: no host reads it. A `.mcp.json` in a plugin that did not select grok is legacy wiring and WARNs |

> **Plugin root**: the plugin root is the directory that *contains* `.claude-plugin/plugin.json`, not `.claude-plugin/` itself. Manifest `skills`, `agents`, and `mcpServers` paths resolve against that root, so `"skills": "./skills/"` points at the root `skills/` directory and is correct even though there are no skills inside `.claude-plugin/`.

## Intent to action mapping

| User intent | Action (call forge.py directly) |
|-------------|--------------------------------|
| create a plugin, scaffold a new plugin | `forge.py create <name> --owner LOGIN --hosts claude,codex,agy,hermes,grok --desc "..."` |
| check a plugin, doctor, validate manifests | `forge.py doctor [PATH] [--fix]` |
| validate the install, does it load locally | `forge.py install <PATH> --host all` |
| publish, push it to GitHub | `forge.py publish [PATH] --owner LOGIN` |
| also register it in a hub marketplace | `forge.py publish [PATH] --owner LOGIN --marketplace OWNER/REPO` |

> The GitHub owner and the hub catalog have **no defaults**. Pass `--owner LOGIN` or set `PLUGIN_FORGE_OWNER`. When empty, create writes a `YOUR_GITHUB_USER` placeholder and publish refuses. The hub (`--marketplace OWNER/REPO` or `PLUGIN_FORGE_MARKETPLACE`) is optional: a generated plugin installs from its own repo (`claude/codex plugin marketplace add owner/name`, `grok plugin install owner/name --trust`).
>
> **`--marketplace OWNER/REPO` updates the chosen hub's per-host manifests.** Each host reads a different file: `.claude-plugin/marketplace.json` (claude), `.agents/plugins/marketplace.json` (codex, which also needs `pluginManifest`, `policy`, and `category` fields), `.grok-plugin/marketplace.json` (grok, which **requires a 40-character sha pin**: registered or refreshed from the pushed HEAD sha, skipped on a dry run, and created when the file is missing; the catalog `name` and `owner` derive from the hub repo, and a new entry prefers the keywords and category from the plugin's `.grok-plugin/plugin.json`), and `.hermes/<name>/plugin.yaml` (hermes, one file per plugin; a plugin without a root `plugin.yaml` gets no stub and is skipped with a WARN, while an existing entry still has its version refreshed). A hub carrying only the Claude file makes `codex plugin add` fail with *not found in marketplace*. Standalone distribution needs no hub at all.
>
> **grok sha pin operations rule**: re-run `publish --marketplace` after every upstream push so the hub catalog sha advances. While the sha points at an old commit, `grok plugin update` keeps fetching that pinned commit, so no amount of pushing changes what gets reinstalled (reproduced when epic-harness stayed pinned at 561e206 and every reinstall pulled the stale version). forge publish refreshes both sha and version on an existing entry.

## Interface policy

- Skills are the only interface. This plugin ships no `commands/` directory, and `create` scaffolds none.
- Every host, Claude Code included, reads this SKILL.md and calls `forge.py` per the intent mapping above.
- New behavior goes into this SKILL.md and `forge.py` only. Do not reintroduce slash commands: a command file restates the skill's arguments, checklists, and host lists, so adding one host then needs N+1 edits and one always gets missed (this happened during the five-host migration, when four command files each needed a manual fix and one was still wrong).

## create details

```bash
forge.py create <name> [--owner LOGIN] [--hosts claude,codex,agy,hermes,grok] [--desc "..."] [--dir PATH]
```

- `--owner` (or `PLUGIN_FORGE_OWNER`): GitHub user or org. **No default.** When empty, manifests and the README get `YOUR_GITHUB_USER` and a WARN.
- `--hosts` selects a subset (default: all five). Manifests for unselected hosts are omitted.
- Selecting hermes writes `plugin.yaml` (YAML) plus an `__init__.py` with a `register(ctx)` stub. hermes uses a YAML manifest rather than JSON, and the plugin directory must contain `__init__.py` ([Hermes plugin spec](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)).
- `skills/<name>/SKILL.md` is the source of truth, and the discovery **directory symlinks** for the selected hosts (`.claude/skills` to `../skills`, and so on) are generated automatically. Add skills only under the root `skills/`: the host folders are links and follow along. A real copy makes doctor WARN, and `--fix` restores the link.
- Write agents to root `agents/<n>.md` (Claude format). The codex variant **must** be rewritten as Codex-native TOML (`.codex-plugin/agents/<n>.toml` with `name`, `description`, `developer_instructions`). doctor checks md-to-toml coverage in both directions.
- Selecting grok writes `.grok-plugin/plugin.json` with flat path keys (skills, agents, plus a documentation-only hooks pointer at root `hooks/hooks.json`). It does not write a `.grok-plugin/marketplace.json`: a standalone self-catalog with a local `"."` source is not listed by the grok browser (measured 1.0.13, plugin_count=0). Ship grok plugins through a hub sha pin (`publish --marketplace`) or direct install (`grok plugin install owner/repo --trust`). When shipping hooks, keep exactly one file at root `hooks/hooks.json` (Claude-compatible schema with `async` removed, and prefer a `command -v` or `sh -c` guard on commands). Do not create a `.grok-plugin/hooks.json` copy: grok never reads it.
- Selecting codex writes `.codex-plugin/plugin.json` and a standalone `.agents/plugins/marketplace.json`. The catalog local path is `./plugins/<name>` (Codex rejects a `"./"` root). `plugins/<name>/` holds dirlinks to the root components, not copies. `doctor --fix` restores a missing catalog or bundle.
- `--mcp`: for an MCP server plugin, also writes a root `mcp_config.json` stub and the host wiring (claude and codex manifest declarations, and a `.mcp.json` file symlink for grok).
- Version is pinned to `0.1.0`; doctor never assigns one.

## doctor checks

1. **Manifest validation**: JSON validity, `$schema`, required fields (name, version, description), and name consistency (the top-level name in a marketplace.json is the market name and is exempt). hermes validates `plugin.yaml` through a stdlib key extractor, with no PyYAML dependency. The grok catalog (`.grok-plugin/marketplace.json`) is checked per entry: a remote source needs a 40-character hex sha plus url, a local source needs an existing path. Absence is not a WARN, since create no longer generates one. This is structural validation only and is separate from actual browser display: a standalone self-catalog can be structurally valid and still go unlisted (measured 1.0.13). The Codex catalog (`.agents/plugins/marketplace.json`) is checked for a local path that starts with `./`, is not the repo root (`"."` or `"./"`), and exists, plus the presence of `policy` and `category`. A `.codex-plugin/marketplace.json` WARNs because Codex does not read it. A catalog name is a market id and is never compared against the plugin name. A `.lsp.json`, if present, is checked for JSON validity only (the schema is undocumented).
2. **Host discovery paths are directory symlinks**: `.claude/skills`, `.codex/skills`, and `.hermes/skills` to `../skills`; `.claude/agents` to `../agents`; `.codex/agents` to `../.codex-plugin/agents`. A real directory (a duplicate) WARNs, and `--fix` deletes it and restores the link. Codex TOML against root md coverage is checked too.
2c. **MCP wiring**: when a root `mcp_config.json` exists, its JSON validity and the claude and codex manifest declarations are checked, and `--fix` wires them. Legacy wiring (`.mcp.json` plus a codex symlink) WARNs and `--fix` migrates it. A root `mcp.json` is a FAIL, since no host reads it.
3. **Structure consistency**: the claude manifest's `skills` (directory), `agents` (file array), and `mcpServers` (file) paths must exist relative to the plugin root. A declared but missing path is a FAIL.
4. **Lifecycle hooks**: checked where hosts differ in path, schema, and events, which is where cross-contamination happens.
   - Shared `hooks/hooks.json`: FAIL when grok is not selected (it is the default for **both** claude and codex, so which one picks it up is undefined). When grok is selected this softens to a WARN, since it is the grok spec location (if claude or codex also ship hooks, declaring an explicit manifest path is strongly recommended), plus JSON validity only, because xAI does not document the event schema.
   - A manifest-declared hook path must exist. Manifest paths are **relative to the plugin root**, so a bare `"hooks.json"` resolves to the agy file and FAILs.
   - An event the host does not support is a FAIL (codex has no `Notification`, agy has only five events).
   - agy hooks must use a **named group** (`{"<name>": {...}}`); claude and codex use `{"hooks": {...}}`.
   - A `register_hook` name in the hermes `__init__.py` must appear in `VALID_HOOKS` (a typo is silently ignored at runtime, so it WARNs).
5. **Install dry run**: per-host manifest discoverability (local structure only, no CLI invoked).
6. **Remote sync**: when `--owner`, `PLUGIN_FORGE_OWNER`, or a git origin is available, `gh api` checks whether the repo exists under that account. The hub registration check runs only with `--marketplace OWNER/REPO` or `PLUGIN_FORGE_MARKETPLACE`; without either, it is skipped.

## Hook file placement per host

| Host | Hook file | Notes |
|------|-----------|-------|
| claude | `.claude-plugin/hooks.json` | Declared through the manifest `hooks` field |
| codex | `.codex-plugin/hooks.json` | Declared through the manifest `hooks` field. No `Notification`; use `PermissionRequest` |
| agy | `hooks.json` (root) | **Forced**: the agy manifest schema is `additionalProperties:false`, so no path can be declared |
| grok | `hooks/hooks.json` | The grok spec location. It collides with the claude and codex default, so doctor keys off whether grok is selected |
| hermes | *(no file)*, `ctx.register_hook(name, fn)` in `__init__.py` | Programmatic registration. The handler is called as `fn(**kwargs)` |

hermes **does** have hooks: 23 entries in `VALID_HOOKS`, including `pre_approval_request` and `post_approval_response`, making it the only one of the five hosts with first-class approval events. An incorrect name is **logged as a warning and then silently ignored**, so doctor checks the names. Real plugins pass names from a collection (`EVENTS`, `HOOK_STATES`), which literal-argument matching never catches, so doctor scans for hook-shaped strings in the file heuristically and reports INFO when it cannot decide.

Only claude substitutes `${CLAUDE_PLUGIN_ROOT}`. codex and claude install into versioned directories (`cache/<market>/<plugin>/<version>/`), so a hook command on another host that points at a bundled script by absolute path has to resolve the version segment at runtime. agy does not use a version directory.

## Honesty principles

- **Dry-run limits**: doctor and install validate local structure and do not guarantee that a host CLI actually loads the plugin. Say so in the results.
- **Remote automation**: publish is fully automated, but it never overwrites an existing remote.
- **No version guessing**: creation pins 0.1.0, and doctor and publish never assign a version.
- **Symlinks are mandatory**: root `skills/` and `agents/` are the single source of truth, and host discovery paths are always directory-level symlinks. Copying skills per host (the toefl-prep style real copy) is forbidden and is an established recurring bug. Codex agents are the one exception: they are converted to TOML, not linked.

## dogfood

plugin-forge is itself built in the five-host layout. Run `forge.py doctor` against this repo and against toefl-prep to confirm the checks hold (both pass with 0 FAIL).

plugin-forge's own `.grok-plugin/marketplace.json` pins this repo's HEAD through a remote url+sha source, which has to be re-pinned every release. Display is measured: a local `"."` self-reference was unlisted (1.0.13, plugin_count=0), and after the switch to remote url+sha it reached plugin_count=1. A standalone url-pinned catalog is therefore a valid distribution path, alongside hub sha pin registration (`publish --marketplace`) and direct install. Note that `catalog_loaded=true` tracks plugin-index.json rich catalogs, so `false` on a standalone catalog is normal.
