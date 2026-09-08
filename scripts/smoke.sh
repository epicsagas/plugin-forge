#!/usr/bin/env bash
# Doctor smoke matrix: fixtures for crash/misfire classes found in review
# (#6). Run locally or from CI. Zero deps — bash + python3 stdlib only.
set -euo pipefail
cd "$(dirname "$0")/.."
FORGE=scripts/forge.py
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

# fixture: independent marketplace (root marketplace.json serves itself)
mkdir -p "$TMP/ind/.claude-plugin"
cat > "$TMP/ind/.claude-plugin/marketplace.json" <<'EOF'
{"name":"ind","plugins":[{"name":"ind","source":"./"}]}
EOF
echo '{"name":"ind","version":"0.1.0","description":"t"}' > "$TMP/ind/.claude-plugin/plugin.json"

# 1. env hub + independent market -> INFO skip, no WARN
out=$(PLUGIN_FORGE_MARKETPLACE=hub/repo python3 "$FORGE" doctor "$TMP/ind" 2>&1) || true
grep -q "independent marketplace" <<<"$out" || fail "env-hub run should skip with INFO"
grep -q "not registered in hub" <<<"$out" && fail "independent market must not WARN"

# 2. explicit --marketplace -> hub check kept, skip suppressed
out=$(PLUGIN_FORGE_MARKETPLACE=hub/repo python3 "$FORGE" doctor "$TMP/ind" --marketplace other/repo 2>&1) || true
grep -q "hub other/repo" <<<"$out" || fail "explicit flag must keep the hub check"
grep -q "independent marketplace" <<<"$out" && fail "explicit flag must override the skip"

# 3. flag without '/' -> resolve_hub falls through to env, same skip decision
out=$(PLUGIN_FORGE_MARKETPLACE=hub/repo python3 "$FORGE" doctor "$TMP/ind" --marketplace local 2>&1) || true
grep -q "independent marketplace" <<<"$out" || fail "flag without / must match resolve_hub (skip)"

# fixture: non-object JSON manifests (regression: AttributeError in cmd_doctor)
mkdir -p "$TMP/bad/.claude-plugin" "$TMP/bad/.codex-plugin" "$TMP/bad/.grok-plugin" "$TMP/bad/hooks"
echo '[1,2,3]' > "$TMP/bad/.claude-plugin/plugin.json"
echo '{"name":"b","version":"0.1.0","description":"t","hooks":"./hooks/hooks.json"}' > "$TMP/bad/plugin.json"
echo '{"name":"b"}' > "$TMP/bad/.claude-plugin/marketplace.json"
echo '[9]' > "$TMP/bad/.codex-plugin/plugin.json"
echo '[9]' > "$TMP/bad/.grok-plugin/plugin.json"
echo '[9]' > "$TMP/bad/hooks/hooks.json"

# 4. arrays everywhere -> FAIL messages, never a traceback
out=$(python3 "$FORGE" doctor "$TMP/bad" 2>&1) || true
grep -qE "Traceback|AttributeError" <<<"$out" && fail "non-object manifest must not crash"
grep -q "JSON object required" <<<"$out" || fail "array manifest should FAIL with object-required message"

# 5. non-list plugins in marketplace.json -> no TypeError
echo '{"name":"ind","plugins":5}' > "$TMP/ind/.claude-plugin/marketplace.json"
out=$(PLUGIN_FORGE_MARKETPLACE=hub/repo python3 "$FORGE" doctor "$TMP/ind" 2>&1) || true
grep -qE "Traceback|TypeError" <<<"$out" && fail "non-list plugins must not crash"

echo "smoke: all fixtures pass"
