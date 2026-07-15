# Contributing to plugin-forge

Thanks for your interest in improving plugin-forge! This guide covers the common ways to contribute.

## Ways to contribute

- 🐛 [Report a bug](https://github.com/epicsagas/plugin-forge/issues/new?template=bug_report.md)
- ✨ [Request a feature](https://github.com/epicsagas/plugin-forge/issues/new?template=feature_request.md)
- 🌍 [Translate the README](README.md) into your language (see `docs/i18n/`)
- 📝 Improve documentation
- 🔧 Submit a pull request

## Development setup

plugin-forge is a single-file Python engine with no runtime dependencies — only the standard library.

```bash
git clone https://github.com/epicsagas/plugin-forge.git
cd plugin-forge
python3 scripts/forge.py --version   # sanity check
```

Requirements:

- Python 3.8+
- `gh` CLI (only needed for `publish` and remote `doctor` checks)

## Before you submit a PR

1. **Run the doctor against the repo itself** — it should report no failures:

   ```bash
   python3 scripts/forge.py doctor
   ```

2. **Run the engine on a throwaway plugin** to make sure nothing regressed:

   ```bash
   python3 scripts/forge.py create scratch-plugin --hosts claude,codex,agy
   python3 scripts/forge.py doctor scratch-plugin/
   ```

3. **Keep manifests in sync.** If you change a manifest template in `scripts/templates/`, the host-discovery copies (`.claude/skills/`, `.codex/skills/`) may need updating. `doctor` will flag drift.

4. **Don't invent versions.** Versions are pinned at create time; don't bump them speculatively in a PR unless that's the explicit change.

## Pull request flow

```bash
git checkout -b fix/my-change
# make changes
python3 scripts/forge.py doctor          # must pass
git commit -m "fix: short description of the change"
git push -u origin fix/my-change
# open a PR against main
```

Please reference any related issue in the PR description (e.g. `Closes #12`).

## Translations

The English `README.md` is the **authoritative source**. Translations live under `docs/i18n/<lang>/README.md`. When opening a translation PR:

- Translate from the latest `README.md` and record the source commit at the top of the file.
- Do **not** translate code blocks, URLs, or badge links.
- Keep technical terms (Claude Code, Codex, agy, manifest) in English where that's the local convention.

## Code style

- Match the existing style in `scripts/forge.py` (standard library only, type hints, small functions).
- No new runtime dependencies — this is a hard constraint (the "zero pip installs" promise).

## Reporting security issues

Please **do not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the private disclosure process.
