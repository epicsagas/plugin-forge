---
description: Scaffold a new multi-host plugin — creates 3-host (claude/codex/agy) manifests, SKILL files, and discovery symlinks using forge.py create.
argument-hint: "<name> [--hosts claude,codex,agy] [--desc \"...\"] [--dir PATH]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-create — Create Plugin

Scaffolds a multi-host plugin with the specified name based on `$ARGUMENTS`.

## Execution

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
python3 "$PLUGIN/scripts/forge.py" create $ARGUMENTS
```

## Arguments

- `<name>` (Required) — lowercase-kebab (`^[a-z0-9-]+$`)
- `--hosts claude,codex,agy` — Subset of hosts to select (default is all). Missing hosts will not get manifests.
- `--desc "..."` — Plugin description (used in manifest description)
- `--display-name "..."` — Codex interface displayName (default = name)
- `--dir PATH` — Target directory (default = `./<name>`)

## Generated Output

- `plugin.json` (agy) + `.claude-plugin/{plugin,marketplace}.json` + `.codex-plugin/plugin.json` (for selected hosts)
- `skills/<name>/SKILL.md` (Source of truth) + `.claude/skills/<name>/`, `.codex/skills/<name>/` symlinks
- `AGENTS.md`, `README.md`, `LICENSE` (MIT), `.gitignore`, `commands/.gitkeep`

## Next Steps

1. Edit `skills/<name>/SKILL.md` (Source of truth)
2. Run `forge.py doctor <dir>` to validate structure
3. Run `forge.py publish <dir> --marketplace` to publish
