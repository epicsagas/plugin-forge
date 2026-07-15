---
description: Validate plugin status — checks manifest validity, schema conformity, discovery symlink synchronization, local install dry-run, and remote status. Fixes symlink drift automatically with --fix.
argument-hint: "[PATH] [--fix]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-doctor — Check Plugin Health

Diagnoses the plugin structure in the directory specified by `$ARGUMENTS` (defaults to current directory).

## Execution

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
python3 "$PLUGIN/scripts/forge.py" doctor $ARGUMENTS
```

## Checklists

1. **Manifest Validation** — JSON validity, `$schema` match, name consistency, and required fields.
2. **Discovery Link Sync** — Verifies relative symbolic links for `.claude/` and `.codex/` skills and agents. Re-links automatically with `--fix`.
3. **Structure Consistency** — Verifies existence of paths specified in `skills`, `commands`, and `agents` within manifests.
4. **Install Dry-run** — Local structure check for host discovery.
5. **Remote Sync** — Validates repo presence via `gh api` and marketplace registration on `epicsagas/plugins`.

## Exit Codes

- 0: No FAIL statuses (warnings are permitted).
- 1: One or more FAIL statuses encountered.

## Design Principles

- Dry-run validation checks local directory layout only — does not invoke target host CLIs.
- Remote check requires `gh` CLI to be installed. Skips with warning if `gh` is missing.
