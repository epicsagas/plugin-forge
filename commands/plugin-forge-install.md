---
description: 플러그인 로컬 설치 검증 — 선택 호스트(claude/codex/agy/all)의 매니페스트가 발견 가능한지 임시 스테이징으로 확인 후 롤백한다.
argument-hint: "<PATH> [--host claude|codex|agy|all] [--keep]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-install — 로컬 설치 검증

`$ARGUMENTS`(플러그인 경로)가 선택 호스트에 설치 가능한지 검증한다.

## 실행

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
"$PLUGIN/scripts/forge.sh" install $ARGUMENTS
```

## 인자

- `<PATH>` (필수) — 플러그인 디렉토리
- `--host claude|codex|agy|all` — 검증 호스트 (기본 all)
- `--keep` — 검증 후 임시 설치본 유지 (기본은 롤백)

## 검증 내용

- claude: `~/.claude/plugins/forge-validate-<name>/`에 복사 후 marketplace.json 발견 가능
- codex: `.codex-plugin/plugin.json` 매니페스트 존재
- agy: 루트 `plugin.json` 유효성

## 정직성 원칙

- "검증"이지 영구 설치 아님 — `--keep` 없으면 롤백.
- 실제 호스트 CLI 로드를 보장하지 않음 — 로컬 구조 발견 가능성만. 결과에 명시.
