---
description: Validate plugin health — thin delegate to the plugin-forge skill.
argument-hint: "[PATH] [--fix]"
allowed-tools: Bash
disable-model-invocation: true
---

Invoke the `plugin-forge` skill and run its **doctor** action with: $ARGUMENTS

The skill's intent→action table and `scripts/forge.py` are the single source of
truth — this command deliberately carries no checklists or host lists.
Update the skill, not this file.
