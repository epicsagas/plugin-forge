# AGENTS.md — plugin-forge

> Shared agent guide. Claude Code, Codex, agy, hermes, and grok all load this file.

## Role

Multi-host plugin manager. Scaffolds new plugins in the 5-host manifest pattern
(root `plugin.json`=agy, `plugin.yaml`=hermes, `.claude-plugin`=claude,
`.codex-plugin`=codex, `.grok-plugin`=grok, host-discovery FOLDER symlinks), runs a doctor that validates
manifests + symlinks + codex TOML coverage + install dry-run + remote,
validates local installability, and publishes to GitHub (optional hub catalog via `--marketplace OWNER/REPO`; no default hub).

The engine `${CLAUDE_PLUGIN_ROOT}/scripts/forge.py` and the intent-to-action table in
`skills/plugin-forge/SKILL.md` are the single source of truth. Every host, Claude Code
included, invokes `forge.py <subcommand>` per that table. The skill is the only
interface: this plugin ships no slash commands, and `create` scaffolds none. New
behavior goes in SKILL.md and forge.py.

## Host differences

- **All hosts**: follow `skills/plugin-forge/SKILL.md` and call `forge.py` directly.
- **grok (Grok Build)**: delivery is direct install
  (`grok plugin install owner/repo --trust`) or a sha-pinned hub catalog entry
  written by publish. Standalone self-catalogs (local ".") are not listed by
  the grok browser (measured 1.0.13), so create does not generate one.

## Manifest pattern (from toefl-prep / byoh)

| File | Host |
|------|------|
| `plugin.json` (root) | agy |
| `.claude-plugin/plugin.json` | Claude Code |
| `.claude-plugin/marketplace.json` | Claude marketplace (source "./") |
| `.codex-plugin/plugin.json` | Codex (interface block); catalog is not here |
| `.agents/plugins/marketplace.json` | Codex standalone catalog (local path `./plugins/<name>`, never `"./"`) |
| `.grok-plugin/plugin.json` | grok (Grok Build) metadata; components are read natively from the plugin root |
| `.grok-plugin/marketplace.json` | grok catalog (hub only: publish writes sha-pinned remote entries; standalone local "." catalogs are not listed by the grok browser, measured 1.0.13) |
| `.codex-plugin/agents/<n>.toml` | Codex-native agents (name / description / developer_instructions) |
| `.claude/skills`, `.codex/skills`, `.hermes/skills`, `.claude/agents` | dir symlinks to the root folders — never copies |
| `mcp_config.json` (root) | MCP single source and the agy plugin spec name: claude/codex manifests declare `mcpServers` pointing at it, agy auto-discovers it, grok reads the root `.mcp.json` **file symlink** to it. Never a real `.mcp.json` copy, never `mcp.json`: no host reads those |

## Dependencies

- `python3` (JSON/YAML validation)
- `gh` CLI (doctor remote checks + publish) — optional for create/doctor-local.

## Honesty

- doctor/install are **dry-run** (local structure checks) — actual host CLI load is not verified.
- publish never overwrites an existing remote repo.
- Versions are pinned at create time (0.1.0); doctor/publish never invent versions.
