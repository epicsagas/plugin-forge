---
description: 새 멀티호스트 플러그인 스캐폴드 — forge.py create로 3호스트(claude/codex/agy) 매니페스트 + SKILL + 발견용 복사본을 생성한다.
argument-hint: "<name> [--hosts claude,codex,agy] [--desc \"...\"] [--dir PATH]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-create — 플러그인 생성

`$ARGUMENTS`로 지정한 이름의 멀티호스트 플러그인을 스캐폴드한다.

## 실행

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
python3 "$PLUGIN/scripts/forge.py" create $ARGUMENTS
```

## 인자

- `<name>` (필수) — 소문자-kebab (`^[a-z0-9-]+$`)
- `--hosts claude,codex,agy` — 부분 선택 (기본 전부). 미선택 호스트 매니페스트는 생성 안 함.
- `--desc "..."` — 플러그인 설명 (매니페스트 description)
- `--display-name "..."` — Codex interface displayName (기본 = name)
- `--dir PATH` — 대상 디렉토리 (기본 `./<name>`)

## 생성 결과

- `plugin.json` (agy) + `.claude-plugin/{plugin,marketplace}.json` + `.codex-plugin/plugin.json` (선택 호스트만)
- `skills/<name>/SKILL.md` (진실 원천) + `.claude/skills/<name>/`, `.codex/skills/<name>/` 복사본
- `AGENTS.md`, `README.md`, `LICENSE`(MIT), `.gitignore`, `commands/.gitkeep`

## 다음 단계

1. `skills/<name>/SKILL.md` 편집 (진실 원천)
2. `forge.py doctor <dir>` 로 점검
3. `forge.py publish <dir> --marketplace` 로 배포

## 정직성 원칙

- 버전은 항상 `0.1.0`으로 생성. doctor/publish가 임의 부여하지 않음.
- 미선택 호스트는 매니페스트를 아예 만들지 않음 — doctor가 "host skipped"로 인식.
