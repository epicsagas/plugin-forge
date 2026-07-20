---
name: plugin-forge
description: >
  멀티호스트(Claude Code·Codex·agy·hermes) 플러그인 매니저. 사용자가 "플러그인
  만들어", "create plugin", "플러그인 점검", "doctor", "플러그인 설치 검증",
  "publish plugin", "마켓 등록" 같은 표현을 쓸 때 사용한다. toefl-prep/byoh에서
  확립한 매니페스트 패턴(루트 plugin.json=agy, plugin.yaml=hermes,
  .claude-plugin=claude, .codex-plugin=codex, 발견용 복사본)으로 생성·점검·
  로컬 설치 검증·리모트 배포를 통합 관리한다.
---

# plugin-forge — 멀티호스트 플러그인 매니저

새 플러그인을 4호스트(claude/codex/agy/hermes) 구조로 스캐폴드하고, 매니페스트를
점검하고, 로컬 설치를 검증하고, GitHub + 마켓플레이스에 배포한다.

> **엔진 위치**: `${CLAUDE_PLUGIN_ROOT}/scripts/forge.py` 가 단일 진실 원천.
> Claude Code는 `commands/` 슬래시 명령, Codex/agy/hermes는 아래 매핑대로 `forge.py` 직접 호출.

## 매니페스트 패턴 (toefl-prep 기준)

| 파일 | 호스트 |
|------|--------|
| `plugin.json` (루트) | agy |
| `plugin.yaml` (루트) | hermes (YAML 매니페스트 + `__init__.py`의 `register(ctx)`) |
| `.claude-plugin/plugin.json` | Claude Code (skills/commands/agents/mcpServers) |
| `.claude-plugin/marketplace.json` | Claude 마켓 (source "./") |
| `.codex-plugin/plugin.json` | Codex (interface 블록) |
| `.claude/skills/<n>/`, `.codex/skills/<n>/`, `.hermes/skills/<n>/` | 로컬 발견용 SKILL 복사본 (symlink) — 마켓플레이스 설치는 루트 `skills/`를 로드 |

> **플러그인 루트**: `.claude-plugin/plugin.json`을 *포함하는* 디렉터리가 플러그인 루트입니다
> (`.claude-plugin/` 자체가 아님). 매니페스트의 `skills`/`commands`/`agents`/`mcpServers`
> 경로는 이 루트 기준으로 해석됩니다. 따라서 `"skills": "./skills/"`는 루트의 `skills/`
> 디렉터리를 가리키며 올바른 구조이고, `.claude-plugin/` 안에 skills가 없어도 정상입니다.

## 의도 → 액션 매핑

| 사용자 의도 | 명령/스크립트 |
|-------------|---------------|
| "플러그인 만들어", "새 플러그인 생성" | `forge.py create <name> --hosts ... --desc ...` / `/plugin-forge-create` |
| "플러그인 점검", "doctor", "매니페스트 검증" | `forge.py doctor [PATH] [--fix]` / `/plugin-forge-doctor` |
| "설치 검증", "로컬에서 로드되나" | `forge.py install <PATH> --host ...` / `/plugin-forge-install` |
| "배포", "깃헙에 올려", "마켓 등록" | `forge.py publish [PATH] [--marketplace]` / `/plugin-forge-publish` |

## create 상세

```bash
forge.py create <name> [--hosts claude,codex,agy,hermes] [--desc "..."] [--dir PATH]
```
- `--hosts`로 부분 선택 (기본 4개 전부). 미선택 호스트는 매니페스트 생략.
- hermes 선택 시 `plugin.yaml`(YAML) + `__init__.py`(`register(ctx)` 스텁) 생성. hermes는
  JSON이 아닌 YAML 매니페스트를 쓰며, 플러그인 디렉터리에 `__init__.py`가 필수다
  ([Hermes plugin spec](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)).
- `skills/<name>/SKILL.md` 가 진실 원천; 선택한 호스트의 발견용 복사본 자동 생성.
- 버전 `0.1.0` 고정, doctor가 임의 부여하지 않음.

## doctor 검사 항목

1. **매니페스트 검증**: JSON 유효성 + `$schema` + 필수 필드(name/version/description) + name 일관성 (marketplace.json 최상위 name=마켓 이름은 제외). hermes는 YAML `plugin.yaml`을 stdlib 키 추출로 검증(PyYAML 의존 없음).
2. **호스트 복사본 동기화**: 루트 `skills/*/SKILL.md` vs `.claude/`·`.codex/`·`.hermes/` (SHA 비교, `--fix`로 재동기화).
3. **구조 일관성**: claude 매니페스트의 `skills`(디렉터리)/`commands`(디렉터리)/`agents`(파일 배열)/`mcpServers`(파일) 경로가 플러그인 루트 기준으로 실제 존재하는지 확인. 선언됐지만 없는 경로는 FAIL.
4. **설치 dry-run**: 각 호스트 매니페스트 발견 가능성 (로컬 구조만, CLI 미실행).
5. **리모트 동기화**: `gh api`로 repo 존재 + `epicsagas/plugins` 마켓 등록 여부.

## 정직성 원칙

- **dry-run 한계**: doctor/install은 로컬 구조 검증이지 실제 호스트 CLI 로드를 보장하지 않음 — 결과에 명시.
- **리모트 자동화**: publish는 전체 자동화 모드지만 remote가 이미 존재하면 덮어쓰지 않음.
- **버전 추정 금지**: 생성 시 0.1.0, doctor/publish가 임의 부여 안 함.
- **복사본 기본**: toefl-prep 패턴(실제 복사). byoh의 심볼릭 패턴은 doctor가 검증만.

## dogfood

plugin-forge 자신도 4호스트 구조로 만들어졌다. `forge.py doctor`를 자기 자신과
toefl-prep에 돌려 검증 기준이 맞는지 확인한다 (둘 다 0 FAIL 통과).
