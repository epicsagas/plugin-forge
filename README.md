# plugin-forge

[English](README.md) | [한국어](docs/i18n/ko/README.md) | [日本語](docs/i18n/ja/README.md) | [简体中文](docs/i18n/zh-Hans/README.md) | [繁體中文](docs/i18n/zh-Hant/README.md) | [Español](docs/i18n/es/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md) | [Português](docs/i18n/pt/README.md) | [Русский](docs/i18n/ru/README.md) | [Italiano](docs/i18n/it/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-6C757D.svg)](#usage)
[![Version](https://img.shields.io/badge/Version-0.2.0-orange.svg)](CHANGELOG.md)
[![Hosts](https://img.shields.io/badge/Hosts-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20agy%20%C2%B7%20hermes%20%C2%B7%20grok-7C3AED.svg)](#manifest-pattern-toefl-prep--byoh)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-stdlib%20only-2EA44F.svg)](#usage)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-FF69B4.svg)](CONTRIBUTING.md)

> Multi-host plugin manager — **Claude Code · Codex · agy · hermes · grok**. Scaffold, doctor, install-validate, and publish plugins from one engine.

Born from the manifest juggling in [toefl-prep](https://github.com/epicsagas/toefl-prep) and byoh: every plugin needs 5+ manifests (root `plugin.json` for agy, root `plugin.yaml` for [hermes](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins), `.claude-plugin/{plugin,marketplace}.json` for Claude, `.codex-plugin/plugin.json` for Codex, `.grok-plugin/{plugin,marketplace}.json` for grok, plus host-discovery SKILL copies). plugin-forge generates them, validates them, checks local installability, and ships to GitHub + the marketplace.

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
claude plugin marketplace add epicsagas/plugin-forge
claude plugin install plugin-forge@plugin-forge

# Codex
codex plugin marketplace add epicsagas/plugin-forge
codex plugin add plugin-forge@plugin-forge

# agy (repo URL, no .git)
agy plugin install https://github.com/epicsagas/plugin-forge
agy plugin enable plugin-forge

# hermes (repo URL)
hermes plugins install https://github.com/epicsagas/plugin-forge
hermes plugins enable plugin-forge
# Blocked by skills_guard (AGENTS.md mention → CRITICAL persistence)?
# Disable the install scan in hermes config: plugins.scan_on_install: false

# grok (Grok Build) — add this repo as a catalog (local source in
# .grok-plugin/marketplace.json), or pin a sha in a hub catalog / PR to
# https://github.com/xai-org/plugin-marketplace
```

## Usage

Cross-platform: runs on Windows / Linux / macOS with any Python 3.8+. Standard library only (no pip installs).

```bash
# Scaffold a 5-host plugin
python3 scripts/forge.py create my-plugin --hosts claude,codex,agy,hermes,grok --desc "Does X"

# Check it (manifests, sync, install dry-run, remote)
python3 scripts/forge.py doctor my-plugin/

# Validate local installability
python3 scripts/forge.py install my-plugin/ --host all

# Publish + register in the suite marketplace
python3 scripts/forge.py publish my-plugin/ --marketplace
```

> On Windows use `py` or `python` instead of `python3`. No bash required.

## Manifest pattern (toefl-prep / byoh)

| File | Host |
|------|------|
| `plugin.json` (root) | agy |
| `plugin.yaml` (root) + `__init__.py` | hermes |
| `.claude-plugin/plugin.json` | Claude Code |
| `.claude-plugin/marketplace.json` | Claude marketplace |
| `.codex-plugin/plugin.json` | Codex |
| `.grok-plugin/plugin.json` | grok (Grok Build) — components are read natively from the plugin root |
| `.grok-plugin/marketplace.json` | grok catalog (local source in this repo; sha-pinned remote in a hub) |
| `.mcp.json` (root) | grok MCP config — file symlink to `mcp_config.json` |
| `.claude/skills/<n>/`, `.codex/skills/<n>/`, `.hermes/skills/<n>/` | discovery copies |

> hermes uses a **YAML** manifest (`plugin.yaml`) and requires an `__init__.py` with a
> `register(ctx)` entry point — distinct from the JSON manifests of the other hosts.
> See the [Hermes plugin spec](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins).
> grok catalog entries (`plugins[]` in a marketplace repo's `.grok-plugin/marketplace.json`)
> must pin the upstream commit **sha**; `publish --marketplace` registers/bumps it from the
> pushed HEAD. See the [xAI plugin marketplace](https://github.com/xai-org/plugin-marketplace).

## Honest limitations

- doctor/install are **dry-run** — they validate local structure, not actual host CLI load.
- publish never overwrites an existing remote.
- Versions are pinned at create (0.1.0); never invented by doctor/publish.

## Updating

`plugin-forge` itself is versioned at create time (currently `0.2.0`). To get the latest:

```bash
# Claude Code
claude plugin update plugin-forge

# Codex
codex plugin update plugin-forge

# agy — re-install from the latest remote
agy plugin install https://github.com/epicsagas/plugin-forge
agy plugin enable plugin-forge

# hermes — re-install from the latest remote
hermes plugins install https://github.com/epicsagas/plugin-forge
hermes plugins enable plugin-forge

# grok — bump the pinned sha in your catalog entry (re-run
# publish --marketplace, or xai-org's bump-plugin-shas.py flow)
```

Check the version:

```bash
python3 scripts/forge.py --version
```

See [CHANGELOG.md](CHANGELOG.md) for changes between releases.

## Community

- 📋 [Contributing](CONTRIBUTING.md)
- 🛡️ [Security policy](SECURITY.md)
- 💬 [Support / Getting help](SUPPORT.md)
- 📜 [Code of Conduct](CODE_OF_CONDUCT.md)

## License

MIT
