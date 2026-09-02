---
description: Validate local installability — thin delegate to the plugin-forge skill.
argument-hint: "<PATH> [--host claude|codex|agy|hermes|grok|all] [--keep]"
allowed-tools: Bash
disable-model-invocation: true
---

Invoke the `plugin-forge` skill and run its **install** action with: $ARGUMENTS

The skill's intent→action table and `scripts/forge.py` are the single source of
truth — this command deliberately carries no validation-scope or host lists.
Update the skill, not this file.
