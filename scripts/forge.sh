#!/usr/bin/env bash
# forge.sh — multi-host plugin manager (create / doctor / install / publish)
#
# Hosts: claude (Claude Code), codex (Codex), agy (Antigravity CLI).
# Authoritative manifest pattern (toefl-prep / ir-search):
#   - plugin.json (root)              -> agy
#   - .claude-plugin/plugin.json      -> Claude Code (skills/commands/agents)
#   - .claude-plugin/marketplace.json -> Claude marketplace (source "./")
#   - .codex-plugin/plugin.json       -> Codex (interface block)
#   - .claude/skills/<n>/, .codex/skills/<n>/ -> host-discovery SKILL copies
#
# Usage:
#   forge.sh create   <name> [--hosts claude,codex,agy] [--desc "..."] [--dir PATH]
#   forge.sh doctor   [PATH] [--fix]
#   forge.sh install  <PATH>  [--host claude|codex|agy|all] [--keep]
#   forge.sh publish  [PATH]  [--marketplace] [--no-push]

set -uo pipefail

FORGE_VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPL_DIR="${SCRIPT_DIR}/templates"
OWNER="${PLUGIN_FORGE_OWNER:-epicsagas}"
MARKETPLACE_REPO="${PLUGIN_FORGE_MARKETPLACE:-${OWNER}/plugins}"

# --- helpers -----------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

json_valid() { python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$1" 2>/dev/null; }

json_get() {  # json_get <file> <key>
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2],''))" "$1" "$2" 2>/dev/null
}

sha_file() { shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'; }

# HOST_ARR is set by cmd_create; has_host checks membership.
HOST_ARR=()
has_host() { local x; for x in "${HOST_ARR[@]}"; do [[ "$x" == "$1" ]] && return 0; done; return 1; }

# Render a template: substitutes __NAME__ __DESC__ __OWNER__ __VERSION__ __DISPLAYNAME__
render() {  # render <tpl> <outfile> NAME DESC DISPLAYNAME
  local tpl="$1" out="$2" name="$3" desc="$4" disp="$5"
  sed -e "s|__NAME__|$name|g" \
      -e "s|__DESC__|$desc|g" \
      -e "s|__DISPLAYNAME__|$disp|g" \
      -e "s|__OWNER__|$OWNER|g" \
      -e "s|__VERSION__|$FORGE_VERSION|g" \
      "$tpl" > "$out"
}

# ============================================================================
# create
# ============================================================================
cmd_create() {
  local name="" desc="A plugin." disp="" dir="" hosts="claude,codex,agy"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --hosts) hosts="$2"; shift 2;;
      --desc)  desc="$2"; shift 2;;
      --dir)   dir="$2"; shift 2;;
      --display-name) disp="$2"; shift 2;;
      -*) die "unknown flag: $1";;
      *) [[ -z "$name" ]] && name="$1" || die "unexpected arg: $1"; shift;;
    esac
  done
  [[ -n "$name" ]] || die "create requires <name>"
  [[ "$name" =~ ^[a-z0-9-]+$ ]] || die "name must be lowercase-kebab"
  [[ -z "$disp" ]] && disp="$name"
  [[ -z "$dir" ]] && dir="./$name"

  IFS=',' read -ra HOST_ARR <<< "$hosts"
  for h in "${HOST_ARR[@]}"; do
    [[ "$h" =~ ^(claude|codex|agy)$ ]] || die "unknown host: $h (claude|codex|agy)"
  done

  mkdir -p "$dir"

  echo "🔨 Creating plugin '$name' (hosts: ${hosts}) -> $dir"

  # --- common: skills/<name>/SKILL.md (source of truth) ---
  mkdir -p "$dir/skills/$name" "$dir/commands"
  touch "$dir/commands/.gitkeep"
  cat > "$dir/skills/$name/SKILL.md" <<EOF
---
name: $name
description: >-
  TODO: one-line description of when this skill triggers. Replace this stub.
---

# $name

> TODO: describe the workflow. This SKILL.md is the authoritative source; the
> host-discovery copies under .claude/skills/ and .codex/skills/ mirror it
> (run \`forge doctor\` to keep them in sync).

## Intents -> actions

| User intent | Action |
|-------------|--------|
| TODO | TODO |
EOF

  # agy: root plugin.json
  if has_host agy; then
    render "$TPL_DIR/plugin.json.agy.tpl" "$dir/plugin.json" "$name" "$desc" "$disp"
  fi

  # claude: .claude-plugin/{marketplace,plugin}.json + discovery copy
  if has_host claude; then
    mkdir -p "$dir/.claude-plugin"
    render "$TPL_DIR/plugin.json.claude.tpl" "$dir/.claude-plugin/plugin.json" "$name" "$desc" "$disp"
    render "$TPL_DIR/marketplace.json.tpl" "$dir/.claude-plugin/marketplace.json" "$name" "$desc" "$disp"
    mkdir -p "$dir/.claude/skills/$name"
    cp "$dir/skills/$name/SKILL.md" "$dir/.claude/skills/$name/SKILL.md"
  fi

  # codex: .codex-plugin/plugin.json + discovery copy
  if has_host codex; then
    mkdir -p "$dir/.codex-plugin"
    render "$TPL_DIR/plugin.json.codex.tpl" "$dir/.codex-plugin/plugin.json" "$name" "$desc" "$disp"
    mkdir -p "$dir/.codex/skills/$name"
    cp "$dir/skills/$name/SKILL.md" "$dir/.codex/skills/$name/SKILL.md"
  fi

  # --- shared scaffolding ---
  cat > "$dir/AGENTS.md" <<EOF
# AGENTS.md — $name

> Shared agent guide. Claude Code, Codex, and agy all load this file.

## Role

TODO: describe what this plugin does. The authoritative workflow is
\`skills/$name/SKILL.md\`. Host-discovery copies live under \`.claude/skills/\`
and \`.codex/skills/\` and must mirror it.

## Host differences

- **Claude Code**: uses \`commands/\` (slash commands) + SKILL.
- **Codex / agy**: no \`commands/\` support — follow SKILL.md intent->action table.
EOF

  cat > "$dir/README.md" <<EOF
# $name

> TODO: replace this stub README. Multi-host plugin (Claude Code · Codex · agy).

## Install

\`\`\`bash
# Claude Code
claude plugin marketplace add $MARKETPLACE_REPO
claude plugin install $OWNER@$name

# Codex
codex plugin marketplace add $MARKETPLACE_REPO
codex plugin add $OWNER@$name

# agy (repo URL, no .git)
agy plugin install https://github.com/$OWNER/$name
agy plugin enable $name
\`\`\`

## License

MIT
EOF

  cat > "$dir/LICENSE" <<'EOF'
MIT License

Copyright (c) 2026 __OWNER__

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF
  sed -i '' "s|__OWNER__|$OWNER|" "$dir/LICENSE" 2>/dev/null || { sed "s|__OWNER__|$OWNER|" "$dir/LICENSE" > "$dir/LICENSE.tmp" && mv "$dir/LICENSE.tmp" "$dir/LICENSE"; }

  cat > "$dir/.gitignore" <<'EOF'
.DS_Store
*.pyc
__pycache__/
scratch/
*-workspace/
EOF

  echo
  echo "✓ Created. Files:"
  (cd "$dir" && find . -type f | sort)
  echo
  echo "Next: edit skills/$name/SKILL.md, then:"
  echo "  forge.sh doctor $dir"
  echo "  forge.sh publish $dir --marketplace"
}

# ============================================================================
# doctor
# ============================================================================
cmd_doctor() {
  local path="." fix=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --fix) fix=1; shift;;
      *) path="$1"; shift;;
    esac
  done
  [[ -d "$path" ]] || die "path not found: $path"

  # infer plugin name from any manifest
  local name=""
  for f in "$path/plugin.json" "$path/.claude-plugin/plugin.json" "$path/.codex-plugin/plugin.json"; do
    [[ -f "$f" ]] && { name=$(json_get "$f" "name"); [[ -n "$name" ]] && break; }
  done
  [[ -n "$name" ]] || die "cannot determine plugin name (no manifest found in $path)"

  local pass=0 warn=0 fail=0
  out() { printf "%-6s %s\n" "$1" "$2"; case "$1" in PASS) pass=$((pass+1));; WARN) warn=$((warn+1));; FAIL) fail=$((fail+1));; esac; }

  echo "🩺 forge doctor — $name ($path)"
  echo

  # 1. manifest validity + schema + name consistency
  local expected_schemas=(
    "plugin.json|https://antigravity.google/schemas/v1/plugin.json"
    ".claude-plugin/plugin.json|https://json.schemastore.org/claude-code-plugin-manifest.json"
    ".claude-plugin/marketplace.json|https://anthropic.com/claude-code/marketplace.schema.json"
  )
  for entry in "${expected_schemas[@]}"; do
    local f="${entry%%|*}" want="${entry##*|}"
    if [[ -f "$path/$f" ]]; then
      if json_valid "$path/$f"; then
        local got=$(json_get "$path/$f" '$schema')
        if [[ -z "$got" || "$got" == "$want" ]]; then
          out PASS "manifest $f valid"
        else
          out WARN "manifest $f schema mismatch (got ${got:-none}, want $want)"
        fi
        local mn=$(json_get "$path/$f" "name")
        # marketplace.json top-level name = marketplace name (e.g. 'epicsagas'), NOT plugin name — skip that check.
        if [[ "$f" != ".claude-plugin/marketplace.json" && -n "$mn" && "$mn" != "$name" ]]; then
          out FAIL "manifest $f name='$mn' != '$name'"
        fi
      else
        out FAIL "manifest $f invalid JSON"
      fi
    fi
  done
  # codex manifest (no strict schema requirement)
  if [[ -f "$path/.codex-plugin/plugin.json" ]]; then
    if json_valid "$path/.codex-plugin/plugin.json"; then
      out PASS "manifest .codex-plugin/plugin.json valid"
      local mn=$(json_get "$path/.codex-plugin/plugin.json" "name")
      [[ -n "$mn" && "$mn" != "$name" ]] && out FAIL "codex manifest name='$mn' != '$name'"
    else
      out FAIL "manifest .codex-plugin/plugin.json invalid JSON"
    fi
  fi

  # required fields on claude plugin manifest
  if [[ -f "$path/.claude-plugin/plugin.json" ]]; then
    for k in name version description; do
      v=$(json_get "$path/.claude-plugin/plugin.json" "$k")
      [[ -z "$v" ]] && out FAIL ".claude-plugin/plugin.json missing '$k'"
    done
  fi

  # 2. host-discovery copy sync. Skill dir name may differ from plugin name
  #    (e.g. plugin 'toefl-prep' has skill dir 'toefl'). Discover the skill dir.
  local skill_dir=""
  if [[ -d "$path/skills" ]]; then
    skill_dir=$(find "$path/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -1)
  fi
  if [[ -n "$skill_dir" && -f "$skill_dir/SKILL.md" ]]; then
    local skill_name=$(basename "$skill_dir")
    local root_sha=$(sha_file "$skill_dir/SKILL.md")
    for host in .claude .codex; do
      local cp="$path/$host/skills/$skill_name/SKILL.md"
      if [[ -f "$cp" ]]; then
        local cp_sha=$(sha_file "$cp")
        if [[ "$cp_sha" == "$root_sha" ]]; then
          out PASS "$host discovery copy in sync"
        else
          out WARN "$host discovery copy drifted"
          [[ "$fix" -eq 1 ]] && { cp "$skill_dir/SKILL.md" "$cp"; out PASS "$host copy re-synced (--fix)"; }
        fi
      fi
    done
  else
    out FAIL "skills/*/SKILL.md (source of truth) missing"
  fi

  # 3. structure consistency: claude manifest points to existing dirs
  if [[ -f "$path/.claude-plugin/plugin.json" ]]; then
    for dirkey in skills commands agents; do
      local dirpath=$(json_get "$path/.claude-plugin/plugin.json" "$dirkey")
      if [[ -n "$dirpath" ]]; then
        local clean="${dirpath#./}"
        [[ -d "$path/$clean" ]] || out WARN ".claude-plugin $dirkey -> $clean not found"
      fi
    done
  fi

  # 4. install dry-run: local structure discoverable (no network / no CLI exec)
  local dry_ok=1
  if [[ -f "$path/plugin.json" ]]; then out PASS "agy: root plugin.json discoverable"; else dry_ok=0; out WARN "agy: no root plugin.json (host may be skipped)"; fi
  if [[ -f "$path/.claude-plugin/marketplace.json" ]]; then out PASS "claude: marketplace.json present (marketplace add works)"; else dry_ok=0; fi
  if [[ -f "$path/.codex-plugin/plugin.json" ]]; then out PASS "codex: manifest present"; else dry_ok=0; out WARN "codex: no .codex-plugin/plugin.json (host may be skipped)"; fi
  out INFO "install dry-run = local structure check only (no host CLI invoked)"

  # 5. remote sync (gh)
  if command -v gh >/dev/null 2>&1; then
    if gh api "repos/$OWNER/$name" >/dev/null 2>&1; then
      out PASS "remote repo $OWNER/$name exists"
      if gh api "repos/$OWNER/$name" --jq '.private' 2>/dev/null | grep -q true; then
        out WARN "remote repo is private (marketplace install needs public)"
      fi
    else
      out WARN "remote repo $OWNER/$name not found (run: forge.sh publish)"
    fi
    # marketplace registration
    if gh api "repos/$MARKETPLACE_REPO/contents/.claude-plugin/marketplace.json" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null | python3 -c "import json,sys; m=json.load(sys.stdin); sys.exit(0 if any(p.get('name')=='$name' for p in m.get('plugins',[])) else 1)" 2>/dev/null; then
      out PASS "registered in marketplace $MARKETPLACE_REPO"
    else
      out WARN "not registered in marketplace $MARKETPLACE_REPO (run: forge.sh publish --marketplace)"
    fi
  else
    out WARN "gh not installed — remote sync checks skipped"
  fi

  echo
  printf "Summary: %d PASS, %d WARN, %d FAIL\n" "$pass" "$warn" "$fail"
  [[ "$fail" -gt 0 ]] && exit 1
  exit 0
}

# ============================================================================
# install (local dry-run validation)
# ============================================================================
cmd_install() {
  local path="" host="all" keep=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host) host="$2"; shift 2;;
      --keep) keep=1; shift;;
      *) path="$1"; shift;;
    esac
  done
  [[ -d "$path" ]] || die "path not found: $path"
  local name=$(json_get "$path/.claude-plugin/plugin.json" "name"); [[ -z "$name" ]] && name=$(json_get "$path/plugin.json" "name")
  [[ -n "$name" ]] || die "cannot determine plugin name"

  local tmp=$(mktemp -d)
  echo "🔧 install validation (dry-run) — $name, host=$host"
  echo "  staging: $tmp"
  local rc=0

  validate_claude() {
    local dest=~/.claude/plugins/forge-validate-$name
    rm -rf "$dest"; mkdir -p "$(dirname "$dest")"
    cp -R "$path" "$dest"
    if [[ -f "$dest/.claude-plugin/marketplace.json" ]]; then
      echo "  claude: marketplace.json loadable -> OK"
    else
      echo "  claude: FAIL (no marketplace.json)"; rc=1
    fi
    [[ "$keep" -eq 0 ]] && rm -rf "$dest"
  }
  validate_codex() {
    local dest=~/.codex/plugins/forge-validate-$name
    mkdir -p "$(dirname "$dest")" 2>/dev/null
    if [[ -f "$path/.codex-plugin/plugin.json" ]]; then
      echo "  codex: manifest loadable -> OK"
    else
      echo "  codex: FAIL (no .codex-plugin/plugin.json)"; rc=1
    fi
  }
  validate_agy() {
    if [[ -f "$path/plugin.json" ]] && json_valid "$path/plugin.json"; then
      echo "  agy: root plugin.json valid -> OK"
    else
      echo "  agy: FAIL (no/invalid root plugin.json)"; rc=1
    fi
  }

  case "$host" in
    claude) validate_claude;;
    codex)  validate_codex;;
    agy)    validate_agy;;
    all)    validate_claude; validate_codex; validate_agy;;
    *) die "unknown host: $host";;
  esac

  rm -rf "$tmp"
  echo
  [[ "$rc" -eq 0 ]] && echo "✓ install structure valid (dry-run — actual host load not verified)" || echo "✗ validation failed"
  echo "NOTE: this validates local structure discoverability only. Real install requires the host CLI."
  exit $rc
}

# ============================================================================
# publish
# ============================================================================
cmd_publish() {
  local path="." do_market=0 no_push=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --marketplace) do_market=1; shift;;
      --no-push) no_push=1; shift;;
      *) path="$1"; shift;;
    esac
  done
  [[ -d "$path" ]] || die "path not found: $path"
  local name=$(json_get "$path/.claude-plugin/plugin.json" "name"); [[ -z "$name" ]] && name=$(json_get "$path/plugin.json" "name")
  [[ -n "$name" ]] || die "cannot determine plugin name"

  command -v gh >/dev/null 2>&1 || die "gh CLI required for publish"

  cd "$path" || die "cannot cd $path"
  echo "🚀 publish — $name"

  # git init if needed
  [[ -d .git ]] || { git init -b main >/dev/null 2>&1; echo "  git initialized"; }
  git add -A
  if ! git diff --cached --quiet; then
    git commit -q -m "chore: initial plugin ($name)" && echo "  committed"
  fi

  local repo="$OWNER/$name"
  if gh api "repos/$repo" >/dev/null 2>&1; then
    echo "  remote $repo exists"
  else
    if [[ "$no_push" -eq 1 ]]; then
      echo "  [dry-run] would: gh repo create $repo --public --source . --push"
    else
      gh repo create "$repo" --public --source . --push >/dev/null 2>&1 && echo "  created $repo" || die "gh repo create failed"
    fi
  fi

  if [[ "$no_push" -eq 0 ]] && git remote get-url origin >/dev/null 2>&1; then
    git push -u origin main 2>&1 | sed 's/^/  /' || echo "  push skipped"
  fi

  # version tag
  local ver=$(json_get "$path/.claude-plugin/plugin.json" "version"); [[ -z "$ver" ]] && ver="0.1.0"
  if [[ "$no_push" -eq 1 ]]; then
    echo "  [dry-run] would tag v$ver"
  else
    git tag "v$ver" >/dev/null 2>&1 && git push origin "v$ver" >/dev/null 2>&1 && echo "  tagged v$ver" || echo "  tag v$ver exists/skipped"
  fi

  # marketplace registration
  if [[ "$do_market" -eq 1 ]]; then
    echo "  registering in marketplace $MARKETPLACE_REPO ..."
    local mtmp=$(mktemp -d)
    if gh repo clone "$MARKETPLACE_REPO" "$mntmp/mpl" >/dev/null 2>&1; then
      local mf="$mntmp/mpl/.claude-plugin/marketplace.json"
      if python3 - "$mf" "$name" "$repo" <<'PY'; then
import json,sys
mf,name,repo=sys.argv[1],sys.argv[2],sys.argv[3]
m=json.load(open(mf))
url=f"https://github.com/{repo}.git"
if not any(p.get('name')==name for p in m.get('plugins',[])):
    m.setdefault('plugins',[]).append({"name":name,"source":{"source":"url","url":url},"description":name})
    json.dump(m,open(mf,'w'),indent=2,ensure_ascii=False)
    open(mf,'a').write('\n')
    print("ADDED")
else:
    print("EXISTS")
PY
        (cd "$mntmp/mpl" && git add -A && git commit -q -m "feat(marketplace): add $name" && { [[ "$no_push" -eq 0 ]] && git push >/dev/null 2>&1 || true; } && echo "  marketplace updated")
      else
        echo "  marketplace: $name already registered"
      fi
    else
      echo "  WARN: cannot clone $MARKETPLACE_REPO — register manually"
    fi
    rm -rf "$mntmp"
  fi

  echo
  echo "Install:"
  echo "  claude plugin marketplace add $MARKETPLACE_REPO && claude plugin install $OWNER@$name"
  echo "  codex plugin marketplace add $MARKETPLACE_REPO && codex plugin add $OWNER@$name"
  echo "  agy plugin install https://github.com/$OWNER/$name && agy plugin enable $name"
}

# ============================================================================
# main
sub="${1:-help}"; shift || true
case "$sub" in
  create)  cmd_create "$@";;
  doctor)  cmd_doctor "$@";;
  install) cmd_install "$@";;
  publish) cmd_publish "$@";;
  help|--help|-h|*)
    sed -n '1,20p' "$0";;
esac
