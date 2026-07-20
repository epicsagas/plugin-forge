# Hermes plugin manifest (YAML).
# Spec: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
# Loaded by `hermes plugins` from ~/.hermes/plugins/<name>/plugin.yaml
name: __NAME__
version: "__VERSION__"
description: "__DESC__"
author:
  name: __OWNER__
  url: https://github.com/__OWNER__
# Hermes discovers bundled skills via ctx.register_skill() in __init__.py;
# this list documents them so forge doctor can verify the bundle.
provides_skills:
  - __NAME__
