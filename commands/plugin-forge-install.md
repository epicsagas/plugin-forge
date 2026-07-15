---
description: Validate local plugin installability — checks if manifests are discoverable on the selected host(claude/codex/agy/all) using temporary staging and then rolls back.
argument-hint: "<PATH> [--host claude|codex|agy|all] [--keep]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-install — Validate Local Installation

Validates whether the plugin at `$ARGUMENTS` (plugin path) can be installed on selected hosts.

## Execution

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
python3 "$PLUGIN/scripts/forge.py" install $ARGUMENTS
```

## Arguments

- `<PATH>` (Required) — Plugin directory path.
- `--host claude|codex|agy|all` — Target host to validate (default: all).
- `--keep` — Keeps the temporary installation copy after validation (default: rollback).

## Validation Scope

- **claude**: Staged copies to `~/.claude/plugins/forge-validate-<name>/` and verifies if `marketplace.json` is loadable.
- **codex**: Verifies existence of `.codex-plugin/plugin.json` manifest.
- **agy**: Verifies validity of root `plugin.json` manifest.

## Design Principles

- This command runs validation, not permanent installation. Rollback occurs automatically unless `--keep` is specified.
- Does not guarantee actual load success inside the host CLI — only checks local discovery structures.
