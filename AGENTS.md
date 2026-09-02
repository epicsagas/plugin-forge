# AGENTS.md — plugin-forge

> Shared agent guide. Claude Code, Codex, agy, hermes, and grok all load this file.

## Role

Multi-host plugin manager. Scaffolds new plugins in the 5-host manifest pattern
(root `plugin.json`=agy, `plugin.yaml`=hermes, `.claude-plugin`=claude,
`.codex-plugin`=codex, `.grok-plugin`=grok, host-discovery FOLDER symlinks), runs a doctor that validates
manifests + symlinks + codex TOML coverage + install dry-run + remote,
validates local installability, and publishes to GitHub (optional hub catalog via `--marketplace OWNER/REPO`; no default hub).

The engine `${CLAUDE_PLUGIN_ROOT}/scripts/forge.py` and the intent→action table in
`skills/plugin-forge/SKILL.md` are the single source of truth. Every host — Claude Code
included — invokes `forge.py <subcommand>` per that table. `commands/plugin-forge-*.md`
are thin delegation stubs (frontmatter + "run the skill's action with $ARGUMENTS");
never derive behavior from them and never duplicate skill content into them.
`doctor` enforces this: a command body over 8 lines, or one that never mentions the
skill, WARNs. New behavior goes in SKILL.md and forge.py — the stubs should not change.

## Host differences

- **All hosts**: follow `skills/plugin-forge/SKILL.md`; slash commands are optional
  aliases that delegate to the skill (see the skill's 커맨드 정책 section).
- **grok (Grok Build)**: reads `commands/` natively too — the stubs' "invoke the skill"
  wording is the intended behavior there as well; catalog install is sha-pinned
  (`.grok-plugin/marketplace.json`), so publish — not a CLI — is the delivery path.

## Manifest pattern (from toefl-prep / byoh)

| File | Host |
|------|------|
| `plugin.json` (root) | agy |
| `.claude-plugin/plugin.json` | Claude Code |
| `.claude-plugin/marketplace.json` | Claude marketplace (source "./") |
| `.codex-plugin/plugin.json` | Codex (interface block); catalog is not here |
| `.agents/plugins/marketplace.json` | Codex standalone catalog (local path `./plugins/<name>`, never `"./"`) |
| `.grok-plugin/plugin.json` | grok (Grok Build) metadata; components are read natively from the plugin root |
| `.grok-plugin/marketplace.json` | grok catalog (create: local source "."; publish: sha-pinned remote) |
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
