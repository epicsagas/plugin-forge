---
name: plugin-forge
description: >
  멀티호스트(Claude Code·Codex·agy·hermes) 플러그인 매니저. 사용자가 "플러그인
  만들어", "create plugin", "플러그인 점검", "doctor", "플러그인 설치 검증",
  "publish plugin", "마켓 등록" 같은 표현을 쓸 때 사용한다. toefl-prep/byoh에서
  확립한 매니페스트 패턴(루트 plugin.json=agy, plugin.yaml=hermes,
  .claude-plugin=claude, .codex-plugin=codex, 발견용 폴더 심볼릭 링크)으로 생성·점검·
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
| `.claude/skills`, `.codex/skills`, `.hermes/skills` | **폴더 심볼릭 링크 → `../skills`** (로컬 발견용). 복사본 아님 — 스킬 복제 금지 |
| `agents/*.md` (루트) | 에이전트 진실 원천 (Claude 마크다운 형식) |
| `.claude/agents` | **폴더 심볼릭 링크 → `../agents`** |
| `.codex-plugin/agents/<n>.toml` | **codex 고유 TOML 변환본** (`name`/`description`/`developer_instructions`). `.codex/agents`는 이 폴더로 심볼릭 링크. 마크다운을 그대로 링크하지 않는다 |

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

> **`--marketplace`는 호스트별 매니페스트 3개를 모두 갱신한다.** 호스트마다 읽는 파일이 다르다:
> `.claude-plugin/marketplace.json`(claude) · `.agents/plugins/marketplace.json`(codex, `pluginManifest`/`policy`/`category` 필드 추가 필요) · `.hermes/<name>/plugin.yaml`(hermes, 플러그인당 파일 1개).
> Claude용만 등록하면 publish는 성공했다고 나오지만 `codex plugin add`는 *not found in marketplace*로 실패한다.

## create 상세

```bash
forge.py create <name> [--hosts claude,codex,agy,hermes] [--desc "..."] [--dir PATH]
```
- `--hosts`로 부분 선택 (기본 4개 전부). 미선택 호스트는 매니페스트 생략.
- hermes 선택 시 `plugin.yaml`(YAML) + `__init__.py`(`register(ctx)` 스텁) 생성. hermes는
  JSON이 아닌 YAML 매니페스트를 쓰며, 플러그인 디렉터리에 `__init__.py`가 필수다
  ([Hermes plugin spec](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)).
- `skills/<name>/SKILL.md` 가 진실 원천; 선택한 호스트의 발견용 **폴더 심볼릭 링크**
  (`.claude/skills` → `../skills` 등)를 자동 생성한다. 스킬을 추가할 땐 루트 `skills/`에만
  쓴다 — 호스트 폴더는 링크라서 자동으로 따라온다. 복사본을 만들면 doctor가 WARN하고
  `--fix`로 링크로 되돌린다.
- 에이전트는 루트 `agents/<n>.md`(Claude 형식)에 쓰고, codex용은 **반드시 codex 고유
  TOML**(`.codex-plugin/agents/<n>.toml`, `name`/`description`/`developer_instructions`
  필드)로 재작성한다. doctor가 md↔toml 커버리지를 양방향 검사한다.
- 버전 `0.1.0` 고정, doctor가 임의 부여하지 않음.

## doctor 검사 항목

1. **매니페스트 검증**: JSON 유효성 + `$schema` + 필수 필드(name/version/description) + name 일관성 (marketplace.json 최상위 name=마켓 이름은 제외). hermes는 YAML `plugin.yaml`을 stdlib 키 추출로 검증(PyYAML 의존 없음).
2. **호스트 발견 경로 = 폴더 심볼릭 링크**: `.claude/skills`·`.codex/skills`·`.hermes/skills` → `../skills`, `.claude/agents` → `../agents`, `.codex/agents` → `../.codex-plugin/agents`. 실제 디렉터리(복제본)가 있으면 WARN, `--fix`가 삭제 후 링크로 교체. codex TOML ↔ 루트 md 커버리지도 검사.
3. **구조 일관성**: claude 매니페스트의 `skills`(디렉터리)/`commands`(디렉터리)/`agents`(파일 배열)/`mcpServers`(파일) 경로가 플러그인 루트 기준으로 실제 존재하는지 확인. 선언됐지만 없는 경로는 FAIL.
4. **라이프사이클 훅**: 호스트마다 경로·스키마·이벤트가 달라 교차 오염이 잘 생기는 지점을 검사한다.
   - 공용 `hooks/hooks.json` 존재 → FAIL (claude·codex **양쪽의 기본값**이라 어느 쪽이 집을지 불확실)
   - 매니페스트가 선언한 훅 경로가 실제로 존재하는지 (매니페스트 경로는 **플러그인 루트 기준**이라 `"hooks.json"`은 agy 파일로 해석됨 → FAIL)
   - 호스트가 지원하지 않는 이벤트 → FAIL (codex엔 `Notification` 없음, agy는 5개 이벤트뿐)
   - agy 훅은 **named group**(`{"<이름>": {...}}`), claude/codex는 `{"hooks": {...}}` 구조인지
   - hermes `__init__.py`의 `register_hook` 이름이 `VALID_HOOKS`에 있는지 (오타는 런타임에 조용히 무시됨 → WARN)
5. **설치 dry-run**: 각 호스트 매니페스트 발견 가능성 (로컬 구조만, CLI 미실행).
6. **리모트 동기화**: `gh api`로 repo 존재 + `epicsagas/plugins` 마켓 등록 여부.

## 호스트별 훅 파일 배치

| 호스트 | 훅 파일 | 비고 |
|--------|---------|------|
| claude | `.claude-plugin/hooks.json` | 매니페스트 `hooks`로 선언 |
| codex | `.codex-plugin/hooks.json` | 매니페스트 `hooks`로 선언. `Notification` 없음 → `PermissionRequest` |
| agy | `hooks.json` (루트) | **강제** — agy 매니페스트 스키마가 `additionalProperties:false`라 경로 선언 불가 |
| hermes | *(파일 없음)* — `__init__.py`의 `ctx.register_hook(name, fn)` | 프로그래밍 방식 등록. 핸들러는 `fn(**kwargs)`로 호출됨 |

hermes는 훅이 **있다**(23개 `VALID_HOOKS`, `pre_approval_request`/`post_approval_response` 포함 — 4호스트 중 승인 이벤트가 1급으로 있는 유일한 호스트). 다만 잘못된 이름을 등록하면 hermes는 **로그 경고만 하고 조용히 무시**하므로 doctor가 이름을 대조한다. 실제 플러그인들은 이름을 컬렉션(`EVENTS`/`HOOK_STATES`)에 담아 넘기므로 리터럴 인자 매칭으로는 잡히지 않는다 — doctor는 파일 내 훅 형태 문자열을 휴리스틱으로 검사하고, 판정 불가면 INFO로 알린다.

`${CLAUDE_PLUGIN_ROOT}`를 치환하는 건 claude뿐이다. codex/claude는 버전별 디렉터리(`cache/<마켓>/<플러그인>/<버전>/`)에 설치되므로, 다른 호스트의 훅 명령에서 번들 스크립트를 절대경로로 가리킬 땐 버전 세그먼트를 런타임에 해석해야 한다. agy는 버전 디렉터리를 쓰지 않는다.

## 정직성 원칙

- **dry-run 한계**: doctor/install은 로컬 구조 검증이지 실제 호스트 CLI 로드를 보장하지 않음 — 결과에 명시.
- **리모트 자동화**: publish는 전체 자동화 모드지만 remote가 이미 존재하면 덮어쓰지 않음.
- **버전 추정 금지**: 생성 시 0.1.0, doctor/publish가 임의 부여 안 함.
- **심볼릭 링크 기본(변경 불가)**: 루트 `skills/`·`agents/`가 단일 진실 원천. 호스트 발견
  경로는 항상 **폴더 단위 심볼릭 링크**다. 호스트별로 스킬을 복제하는 것(toefl-prep식
  실제 복사)은 금지 — 이미 확립된 재발 버그. codex 에이전트만 예외: TOML로 "변환"하지
  링크하지 않는다.

## dogfood

plugin-forge 자신도 4호스트 구조로 만들어졌다. `forge.py doctor`를 자기 자신과
toefl-prep에 돌려 검증 기준이 맞는지 확인한다 (둘 다 0 FAIL 통과).
