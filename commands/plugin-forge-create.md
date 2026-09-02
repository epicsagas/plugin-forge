---
description: Create a new multi-host plugin — thin delegate to the plugin-forge skill.
argument-hint: "<name> [--hosts claude,codex,agy,hermes,grok] [--desc \"...\"] [--dir PATH] [--mcp]"
allowed-tools: Bash
disable-model-invocation: true
---

Invoke the `plugin-forge` skill and run its **create** action with: $ARGUMENTS

The skill's intent→action table and `scripts/forge.py` are the single source of
truth — this command deliberately carries no arguments docs, checklists, or
host lists. Update the skill, not this file.
