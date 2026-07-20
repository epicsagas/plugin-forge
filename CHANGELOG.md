# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2026-07-20

### Added
- **hermes (Nous Research) host support** — 4th target host alongside claude/codex/agy.
  - New `plugin.yaml` YAML manifest template (`scripts/templates/plugin.yaml.hermes.tpl`) at the plugin root, plus an `__init__.py` stub with `register(ctx)` (required by the [Hermes plugin spec](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)).
  - `create --hosts ...,hermes` scaffolds the YAML manifest, `__init__.py`, and `.hermes/skills/<n>/` discovery symlink.
  - `doctor` validates the YAML manifest via stdlib-only key extraction (no PyYAML dependency) and checks `.hermes/` discovery sync.
  - `install --host hermes` stages into `~/.hermes/plugins/forge-validate-<name>/` and verifies `plugin.yaml` + `__init__.py`.
  - `publish` prints the `hermes plugins install` / `enable` commands.

### Changed
- `VALID_HOSTS` now includes `hermes`; `--hosts` default is `claude,codex,agy,hermes`.

## [0.1.2] - 2026-07-15

### Fixed
- `doctor` step-3 structure check now validates `agents` (array of file paths) and `mcpServers` (file) relative to the plugin root, and FAILs on a declared-but-missing path instead of silently skipping it. Correctly-structured plugins (e.g. byoh) are no longer falsely flagged as broken. (Fixes #3)

## [0.1.1] - 2026-07-15

### Added
- `--version` flag on `forge.py` to print the engine version.
- Community files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`.
- Multilingual README structure under `docs/i18n/<lang>/`.
- Issue and pull request templates.

### Fixed
- Fixed variable shadowing in `scripts/forge.py` `doctor` command that bypassed Claude plugin structure consistency checks.
- Track `.codex` host-discovery copy (was blocked by global gitignore).

### Changed
- Ported engine from `forge.sh` to `forge.py` (cross-platform, standard library only).

## [0.1.0] - 2026-07-15

### Added
- `create <name> [--hosts ...]` — scaffold a plugin with selected hosts' manifests, SKILL, and discovery copies.
- `doctor [PATH] [--fix]` — validate manifests, sync host copies, structure check, install dry-run, remote sync.
- `install <PATH> [--host ...]` — validate local installability per host (staging + rollback).
- `publish [PATH] [--marketplace]` — git init + `gh repo create` + push + tag + marketplace registration.
- Cross-platform engine ported from `forge.sh` to `forge.py` (standard library only).
- Multi-host manifest pattern: root `plugin.json` (agy), `.claude-plugin/` (Claude), `.codex-plugin/` (Codex), host-discovery SKILL copies.

[Unreleased]: https://github.com/epicsagas/plugin-forge/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/epicsagas/plugin-forge/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/epicsagas/plugin-forge/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/epicsagas/plugin-forge/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/epicsagas/plugin-forge/releases/tag/v0.1.0
