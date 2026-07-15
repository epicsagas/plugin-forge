# plugin-forge

**[English](README.md)**

> Multi-host plugin manager — **Claude Code · Codex · agy**. Scaffold, doctor, install-validate, and publish plugins from one engine.

Born from the manifest juggling in [toefl-prep](https://github.com/epicsagas/toefl-prep) and byoh: every plugin needs 5+ manifests (root `plugin.json` for agy, `.claude-plugin/{plugin,marketplace}.json` for Claude, `.codex-plugin/plugin.json` for Codex, plus host-discovery SKILL copies). plugin-forge generates them, validates them, checks local installability, and ships to GitHub + the marketplace.

## Commands

| Subcommand | What it does |
|------------|--------------|
| `create <name> [--hosts ...]` | Scaffold a new plugin with selected hosts' manifests + SKILL + discovery copies |
| `doctor [PATH] [--fix]` | Validate manifests, sync host copies, structure check, install dry-run, remote sync |
| `install <PATH> [--host ...]` | Validate local installability per host (staging + rollback) |
| `publish [PATH] [--marketplace]` | git init + gh repo create + push + tag + marketplace registration |

## Install

```bash
# Claude Code
claude plugin marketplace add epicsagas/plugins
claude plugin install epicsagas@plugin-forge

# Codex
codex plugin marketplace add epicsagas/plugins
codex plugin add epicsagas@plugin-forge

# agy (repo URL, no .git)
agy plugin install https://github.com/epicsagas/plugin-forge
agy plugin enable plugin-forge
```

## Usage

```bash
# Scaffold a 3-host plugin
forge.sh create my-plugin --hosts claude,codex,agy --desc "Does X"

# Check it (manifests, sync, install dry-run, remote)
forge.sh doctor my-plugin/

# Validate local installability
forge.sh install my-plugin/ --host all

# Publish + register in the suite marketplace
forge.sh publish my-plugin/ --marketplace
```

## Manifest pattern (toefl-prep / byoh)

| File | Host |
|------|------|
| `plugin.json` (root) | agy |
| `.claude-plugin/plugin.json` | Claude Code |
| `.claude-plugin/marketplace.json` | Claude marketplace |
| `.codex-plugin/plugin.json` | Codex |
| `.claude/skills/<n>/`, `.codex/skills/<n>/` | discovery copies |

## Honest limitations

- doctor/install are **dry-run** — they validate local structure, not actual host CLI load.
- publish never overwrites an existing remote.
- Versions are pinned at create (0.1.0); never invented by doctor/publish.

## License

MIT
