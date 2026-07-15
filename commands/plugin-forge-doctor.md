---
description: 플러그인 상태 점검 — 매니페스트 유효성·스키마·복사본 동기화·설치 dry-run·리모트 동기화를 검사한다. --fix로 복사본 드리프트 자동 수정.
argument-hint: "[PATH] [--fix]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-doctor — 상태 점검

`$ARGUMENTS`(경로, 기본 현재 디렉토리)의 플러그인 구조를 점검한다.

## 실행

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
python3 "$PLUGIN/scripts/forge.py" doctor $ARGUMENTS
```

## 검사 항목

1. **매니페스트 검증** — 각 매니페스트 JSON 유효성 + `$schema` + name 일관성 + 필수 필드.
2. **호스트 복사본 동기화** — 루트 `skills/*/SKILL.md` vs `.claude/`·`.codex/` SHA 비교. `--fix`면 재복사.
3. **구조 일관성** — claude 매니페스트 skills/commands/agents 경로 존재.
4. **설치 dry-run** — 각 호스트 매니페스트 발견 가능성 (로컬 구조만).
5. **리모트 동기화** — `gh api`로 repo 존재 + `epicsagas/plugins` 마켓 등록 여부.

## 종료 코드

- 0: FAIL 없음 (WARN은 허용)
- 1: FAIL 존재

## 정직성 원칙

- dry-run은 로컬 구조 검증 — 실제 `claude`/`codex`/`agy` CLI를 실행하지 않음. 결과에 명시.
- 리모트 검사는 `gh` 설치 시에만. 미설치면 WARN으로 스킵.
