---
description: 플러그인 리모트 배포 — gh repo create + push + 버전 태그 + (옵션) epicsagas/plugins 마켓플레이스 등록을 수행한다.
argument-hint: "[PATH] [--marketplace] [--no-push]"
allowed-tools: Bash
disable-model-invocation: true
---

# /plugin-forge-publish — 리모트 배포

`$ARGUMENTS`(경로)의 플러그인을 GitHub에 배포한다.

## 실행

```bash
PLUGIN=~/.claude/plugins/marketplaces/plugin-forge
"$PLUGIN/scripts/forge.sh" publish $ARGUMENTS
```

## 인자

- `[PATH]` — 플러그인 디렉토리 (기본 현재)
- `--marketplace` — `epicsagas/plugins` 마켓플레이스에 등록 (중복 시 스킵)
- `--no-push` — dry-run: 실제 push/생성 없이 명령만 안내

## 수행 단계

1. `git init` (이미 repo면 스킵) + 변경사항 커밋
2. `gh repo create epicsagas/<name> --public --source . --push` (remote 있으면 스킵)
3. `origin/main` push
4. 버전 태그 `v<version>` (매니페스트 version, 기본 0.1.0)
5. `--marketplace`: `epicsagas/plugins` 클론 → marketplace.json에 항목 추가 → push

## 정직성 원칙

- **전체 자동화 모드**지만 remote가 이미 존재하면 덮어쓰지 않음 (경고).
- `--no-push`로 모든 파괴적 동작을 미리보기 가능.
- 마켓 등록은 PR 또는 직접 push — 권한에 따라.
- 배포 후 설치 명령 3호스트분 출력.
