# AGENTS.md — plugin-forge

> Shared agent guide. Claude Code, Codex, and agy all load this file.

## Role

Multi-host plugin manager. Scaffolds new plugins in the 4-host manifest pattern
(root `plugin.json`=agy, `plugin.yaml`=hermes, `.claude-plugin`=claude,
`.codex-plugin`=codex, host-discovery FOLDER symlinks), runs a doctor that validates
manifests + symlinks + codex TOML coverage + install dry-run + remote,
validates local installability, and publishes to GitHub + the `epicsagas/plugins` marketplace.

The engine `${CLAUDE_PLUGIN_ROOT}/scripts/forge.py` is the single source of truth.
Claude Code uses `commands/` (slash commands); Codex/agy call `forge.py` directly per
the intent→action table in `skills/plugin-forge/SKILL.md`.

## Host differences

- **Claude Code**: `/plugin-forge-create`, `/plugin-forge-doctor`, `/plugin-forge-install`, `/plugin-forge-publish`.
- **Codex / agy**: no `commands/` support — invoke `forge.py <subcommand>` directly.

## Manifest pattern (from toefl-prep / byoh)

| File | Host |
|------|------|
| `plugin.json` (root) | agy |
| `.claude-plugin/plugin.json` | Claude Code |
| `.claude-plugin/marketplace.json` | Claude marketplace (source "./") |
| `.codex-plugin/plugin.json` | Codex (interface block) |
| `.codex-plugin/agents/<n>.toml` | Codex-native agents (name / description / developer_instructions) |
| `.claude/skills`, `.codex/skills`, `.hermes/skills`, `.claude/agents` | dir symlinks to the root folders — never copies |
| `mcp_config.json` (root) | MCP single source and the agy plugin spec name: claude/codex manifests declare `mcpServers` pointing at it, agy auto-discovers it. Never `.mcp.json`/`mcp.json`: agy reads only `mcp_config.json` |

## Dependencies

- `python3` (JSON/YAML validation)
- `gh` CLI (doctor remote checks + publish) — optional for create/doctor-local.

## Honesty

- doctor/install are **dry-run** (local structure checks) — actual host CLI load is not verified.
- publish never overwrites an existing remote repo.
- Versions are pinned at create time (0.1.0); doctor/publish never invent versions.
