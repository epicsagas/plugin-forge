---
description: Deploy plugin to remote — executes gh repo create, commits modifications, pushes version tags, and registers to epicsagas/plugins marketplace (optional).
argument-hint: "[PATH] [--marketplace] [--no-push]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-publish — Remote Publish

Publishes the plugin at `$ARGUMENTS` (defaults to current directory) to GitHub and registers it to the marketplace.

## Execution

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
python3 "$PLUGIN/scripts/forge.py" publish $ARGUMENTS
```

## Arguments

- `[PATH]` — Plugin directory path (defaults to current directory).
- `--marketplace` — Registers the plugin to the `epicsagas/plugins` marketplace repository.
- `--no-push` — Dry-run mode: prints commands without executing pushes or creating repositories.

## Workflow

1. Runs `git init` (if not initialized) and commits changes.
2. Runs `gh repo create epicsagas/<name> --public --source . --push` (skipped if remote already exists).
3. Pushes to `origin/main`.
4. Creates and pushes version tag `v<version>` (read from plugin manifest, defaults to `0.1.0`).
5. `--marketplace`: Clones `epicsagas/plugins`, appends metadata to `marketplace.json`, commits and pushes.

## Design Principles

- Uses full-automation mode but does not overwrite if remote repository already exists.
- The `--no-push` flag previews all destructive or remote operations safely.
- Output commands provide direct installation commands for all 4 target hosts.
