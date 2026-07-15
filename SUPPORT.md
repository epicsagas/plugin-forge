# Support

## Getting help

| If you... | Then |
|-----------|------|
| Found a bug | [Open a bug report](https://github.com/epicsagas/plugin-forge/issues/new?template=bug_report.md) |
| Have a feature idea | [Open a feature request](https://github.com/epicsagas/plugin-forge/issues/new?template=feature_request.md) |
| Have a usage question | [Start a discussion](https://github.com/epicsagas/plugin-forge/discussions) (if enabled) or open a question issue |
| Found a security issue | See [SECURITY.md](SECURITY.md) — **do not** open a public issue |

## Before reporting

Please run the doctor and include its output so we can see the exact state:

```bash
python3 scripts/forge.py doctor <your-plugin-path>
python3 scripts/forge.py --version
```

Mention:

- Operating system (Windows / Linux / macOS)
- Python version (`python3 --version`)
- Host and host CLI version (Claude Code / Codex / agy), if relevant
- Whether `gh` CLI is installed (`gh --version`)

## Honest expectations

plugin-forge is maintained as a small, dependency-free tool. `doctor` and `install` are **dry-run** checks — if your issue is that a plugin doesn't actually load inside a host CLI, that's outside what the dry-run can detect. Please still report it, but note which host and the exact error the host prints.
