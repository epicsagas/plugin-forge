# Security Policy

## Supported versions

plugin-forge is early-stage (0.x). Security fixes are applied to the latest `main` and released as a patch version; older 0.x lines are not maintained separately.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, use one of these private channels:

1. **GitHub Private Security Advisory** (preferred):
   [github.com/epicsagas/plugin-forge/security/advisories/new](https://github.com/epicsagas/plugin-forge/security/advisories/new)
2. Email the maintainers via the address listed on the repository profile.

Please include:

- A description of the issue and its potential impact
- Steps to reproduce
- Affected version (`python3 scripts/forge.py --version`)

We will acknowledge receipt within **72 hours** and aim to issue a fix within **30 days** for high-severity issues, coordinated with you on disclosure timing.

## What `publish` does (and does not) do

- `publish` runs `gh repo create`, pushes, and tags — it **never overwrites an existing remote repository**.
- It does **not** push credentials, tokens, or `.env` files. Keep secrets out of the repository and rely on `.gitignore` + your own secret-scanning tooling (e.g., `gitleaks`) before pushing.
- `doctor` / `install` are **dry-run** checks on local file structure only — they do not execute the host CLIs or load any plugin code.

## Scope

This policy covers the code in this repository. Plugins *created by* plugin-forge are separate projects and must define their own security posture.
