---
description: Publish to GitHub + marketplace — thin delegate to the plugin-forge skill.
argument-hint: "[PATH] [--marketplace] [--no-push]"
allowed-tools: Bash
disable-model-invocation: true
---

Invoke the `plugin-forge` skill and run its **publish** action with: $ARGUMENTS

The skill's intent→action table and `scripts/forge.py` are the single source of
truth — this command deliberately carries no workflow steps or host lists.
Update the skill, not this file.
