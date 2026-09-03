---
name: plugin-forge
description: >
  멀티호스트(Claude Code·Codex·agy·hermes·grok) 플러그인 매니저. 사용자가 "플러그인
  만들어", "create plugin", "플러그인 점검", "doctor", "플러그인 설치 검증",
  "publish plugin", "마켓 등록" 같은 표현을 쓸 때 사용한다. toefl-prep/byoh에서
  확립한 매니페스트 패턴(루트 plugin.json=agy, plugin.yaml=hermes,
  .claude-plugin=claude, .codex-plugin=codex, .grok-plugin=grok, 발견용 폴더 심볼릭
  링크)으로 생성·점검· 로컬 설치 검증·리모트 배포를 통합 관리한다.
---

# plugin-forge — 멀티호스트 플러그인 매니저

새 플러그인을 5호스트(claude/codex/agy/hermes/grok) 구조로 스캐폴드하고, 매니페스트를
점검하고, 로컬 설치를 검증하고, GitHub + 마켓플레이스에 배포한다.

> **엔진 위치**: `${CLAUDE_PLUGIN_ROOT}/scripts/forge.py` 가 단일 진실 원천.
> **모든 호스트가 이 스킬을 따른다** — 아래 매핑대로 `forge.py`를 직접 호출한다.
> `commands/` 슬래시 명령은 이 스킬을 가리키는 얇은 위임 스텁일 뿐이므로 **커맨드를
> 근거로 동작을 파생시키지 않는다** (아래 "커맨드 정책" 참조).

## 매니페스트 패턴 (toefl-prep 기준)

| 파일 | 호스트 |
|------|--------|
| `plugin.json` (루트) | agy |
| `plugin.yaml` (루트) | hermes (YAML 매니페스트 + `__init__.py`의 `register(ctx)`) |
| `.claude-plugin/plugin.json` | Claude Code (skills/commands/agents/mcpServers) |
| `.claude-plugin/marketplace.json` | Claude 마켓 (source "./") |
| `.codex-plugin/plugin.json` | Codex (interface 블록). 이 폴더에는 plugin.json만. 카탈로그는 아래 |
| `.agents/plugins/marketplace.json` | Codex 단독 마켓. create가 `./plugins/<name>` 로컬 소스로 생성 (Codex는 `"./"` 루트를 거부). `plugins/<name>/`는 루트 `.codex-plugin`·`skills` 등으로의 디링크 |
| `.grok-plugin/plugin.json` | grok (xAI Grok Build) 메타데이터 매니페스트. 컴포넌트(`skills/`·`commands/`·`agents/`)는 **플러그인 루트에서 네이티브로 읽음** — 발견용 심볼릭 링크 불필요. flat 경로 키만 유효(`"skills": "./skills/"` 스타일), `components` 객체는 무시됨(1.0.13 실측). hooks는 루트 `hooks/hooks.json`이 유일 로드 경로(A/B 삭제 실측)라 매니페스트 hooks 키는 문서용 참조. 훅 스키마는 Claude 호환(이벤트·matcher 동일)이되 `async` 필드 없음, `GROK_PLUGIN_ROOT` 환경변수 주입. [xAI 카탈로그 참조](https://github.com/xai-org/plugin-marketplace) |
| `.grok-plugin/marketplace.json` | grok 카탈로그. **create는 생성하지 않음**(푸시 전엔 핀할 sha가 없음): standalone 카탈로그는 remote url+sha 소스로 유효하다. 자기 리포 HEAD를 핀한 standalone 카탈로그도 브라우저 표시 확인됨(1.0.13 실측, plugin_count=1). local `"."` 자기참조는 미표시(같은 버전 실측, 0)라 doctor가 WARN, 서브디렉터리 local은 구조만 검증(표시 보장 아님) |
| `.claude/skills`, `.codex/skills`, `.hermes/skills` | **폴더 심볼릭 링크 → `../skills`** (로컬 발견용). 복사본 아님 — 스킬 복제 금지 |
| `agents/*.md` (루트) | 에이전트 진실 원천 (Claude 마크다운 형식) |
| `.claude/agents` | **폴더 심볼릭 링크 → `../agents`** |
| `.codex-plugin/agents/<n>.toml` | **codex 고유 TOML 변환본** (`name`/`description`/`developer_instructions`). `.codex/agents`는 이 폴더로 심볼릭 링크. 마크다운을 그대로 링크하지 않는다 |
| `mcp_config.json` (루트) | **MCP 단일 원천, agy 스펙 파일명**(Antigravity 플러그인 스펙). claude는 매니페스트에 `mcpServers: ["./mcp_config.json"]` 선언, codex는 `mcpServers: "./mcp_config.json"` 선언, agy는 루트 자동 발견(배선 불필요), grok은 루트 `.mcp.json`을 **`mcp_config.json`으로 파일 심볼릭 링크**(grok 스펙이 읽는 이름), hermes는 MCP 파일 규약 없음. 루트에 `mcp.json`을 만들지 않는다: 어느 호스트도 읽지 않는다. `.mcp.json`은 grok 미선택 플러그인에서 구배선(legacy)으로 WARN |

> **플러그인 루트**: `.claude-plugin/plugin.json`을 *포함하는* 디렉터리가 플러그인 루트입니다
> (`.claude-plugin/` 자체가 아님). 매니페스트의 `skills`/`commands`/`agents`/`mcpServers`
> 경로는 이 루트 기준으로 해석됩니다. 따라서 `"skills": "./skills/"`는 루트의 `skills/`
> 디렉터리를 가리키며 올바른 구조이고, `.claude-plugin/` 안에 skills가 없어도 정상입니다.

## 의도 → 액션 매핑

| 사용자 의도 | 액션 (forge.py 직접 호출) |
|-------------|--------------------------|
| "플러그인 만들어", "새 플러그인 생성" | `forge.py create <name> --owner LOGIN --hosts claude,codex,agy,hermes,grok --desc "..."` |
| "플러그인 점검", "doctor", "매니페스트 검증" | `forge.py doctor [PATH] [--fix]` |
| "설치 검증", "로컬에서 로드되나" | `forge.py install <PATH> --host all` |
| "배포", "깃헙에 올려" | `forge.py publish [PATH] --owner LOGIN` |
| "허브 마켓에도 등록" | `forge.py publish [PATH] --owner LOGIN --marketplace OWNER/REPO` |

> 슬래시 명령(`/plugin-forge-create` 등)을 받았으면 커맨드 파일을 해석하지 말고
> 이 표의 동일 액션을 그대로 실행한다. 커맨드는 진입점일 뿐이다.

> GitHub owner와 허브 카탈로그는 **기본값이 없다.** `--owner LOGIN` 또는 `PLUGIN_FORGE_OWNER`. 비우면 create는 `YOUR_GITHUB_USER` 자리표시를 넣고, publish는 거부한다. 허브(`--marketplace OWNER/REPO` 또는 `PLUGIN_FORGE_MARKETPLACE`)는 옵션이다. 생성 플러그인의 설치 경로는 그 플러그인 레포 자체(`claude/codex plugin marketplace add owner/name`, `grok plugin install owner/name --trust`)다.
>
> **`--marketplace OWNER/REPO`는 선택한 허브의 호스트별 매니페스트를 갱신한다.** 허브마다 읽는 파일이 다르다:
> `.claude-plugin/marketplace.json`(claude) · `.agents/plugins/marketplace.json`(codex, `pluginManifest`/`policy`/`category` 필드 추가 필요) · `.grok-plugin/marketplace.json`(grok, **40자리 sha 핀 필수** — 푸시된 HEAD sha로 등록/갱신, 드라이런은 스킵, 파일 없으면 생성. 이때 카탈로그 `name`/`owner`는 허브 레포에서 유도하고 새 엔트리의 keywords/category는 플러그인 `.grok-plugin/plugin.json` 값을 우선 사용) · `.hermes/<name>/plugin.yaml`(hermes, 플러그인당 파일 1개. 루트 `plugin.yaml` 없는 플러그인은 스텁을 만들지 않고 스킵 WARN — 기존 엔트리의 버전 갱신은 유지).
> 허브에 Claude용만 있으면 `codex plugin add`는 *not found in marketplace*로 실패한다. 독립 배포에는 허브가 필요 없다.
>
> **grok sha 핀 운영 규칙:** 업스트림에 push할 때마다 `publish --marketplace`를 재실행해 허브 카탈로그의 sha를 갱신해야 한다. sha가 구 커밋에 머물면 `grok plugin update`는 고정 sha만 다시 받으므로 아무리 push해도 재설치는 구 커밋이다(재현: epic-harness가 561e206에 고정돼 재설치가 계속 구 버전을 받던 사례. forge publish는 기존 엔트리의 sha·version을 자동 갱신한다).

## 커맨드 정책

- `commands/plugin-forge-*.md`는 **스킬 위임 스텁** 이상이어서는 안 된다: frontmatter
  (description·argument-hint·allowed-tools) + "plugin-forge 스킬의 해당 액션을
  $ARGUMENTS로 실행" 한 줄. 그 외 내용 금지.
- 인자 문서·체크리스트·검증 범위·호스트 목록을 커맨드에 **복제하지 않는다**.
  커맨드가 스킬 내용을 복제하면 호스트 하나 추가할 때마다 5곳을 고쳐야 하고,
  어느 순간 어긋난다(실제로 5호스트 전환 때 4개 커맨드 파일을 전부 수동 고침).
- 새 지침·새 동작은 **항상 이 SKILL.md와 forge.py에만** 추가한다. 커맨드 스텁은
  수정할 일이 없어야 정상이다.
- 스킬 기반 동작이 기본 경로다. 커맨드는 사용자의 슬래시 습관을 위한 별칭일 뿐이며,
  모델은 커맨드 유무와 무관하게 이 스킬의 매핑대로 `forge.py`를 호출한다.
- **doctor가 이 규칙을 강제한다**: 커맨드 본문(frontmatter 제외)이 8줄을 넘거나
  "skill"을 한 번도 언급하지 않으면 WARN. `commands/README.md`는 규칙 문서라 예외.
- `create`는 빈 `commands/` 대신 이 규칙을 적은 `commands/README.md`를 깔아둔다.
  빈 디렉터리가 곧 두 번째 스펙을 짓기 시작하는 자리이기 때문이다.

## create 상세

```bash
forge.py create <name> [--owner LOGIN] [--hosts claude,codex,agy,hermes,grok] [--desc "..."] [--dir PATH]
```
- `--owner` (또는 `PLUGIN_FORGE_OWNER`): GitHub user/org. **기본값 없음.** 비우면 매니페스트·README에 `YOUR_GITHUB_USER`를 넣고 WARN.
- `--hosts`로 부분 선택 (기본 5개 전부). 미선택 호스트는 매니페스트 생략.
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
- grok 선택 시 `.grok-plugin/plugin.json`을 생성한다(flat 경로 키 포함: skills/commands/agents + hooks는 루트 `hooks/hooks.json` 문서 참조). 자체 `.grok-plugin/marketplace.json`은 생성하지 않는다: standalone self-catalog(local `"."`)는 grok 브라우저가 미표시(1.0.13 실측, plugin_count=0). grok 배포는 허브 sha 핀 등록(`publish --marketplace`) 또는 direct install(`grok plugin install owner/repo --trust`). hooks를 배포할 때는 루트 `hooks/hooks.json` 하나만 둔다(Claude 호환 스키마에서 `async` 제거, 커맨드에 `command -v`/`sh -c` 가드 권장) — `.grok-plugin/hooks.json` 사본은 grok가 안 읽으니 만들지 않는다.
- codex 선택 시 `.codex-plugin/plugin.json`과 단독 `.agents/plugins/marketplace.json`을 생성한다. 카탈로그 local path는 `./plugins/<name>` (루트 `"./"`는 Codex가 거부). `plugins/<name>/`는 루트 컴포넌트로의 디링크이며 복사본이 아니다. doctor `--fix`가 빠진 카탈로그·번들을 보충한다.
- `--mcp` 플래그: MCP 서버 플러그인이면 루트 `mcp_config.json` 스텁 + 호스트 배선(claude·codex
  매니페스트 선언, grok은 `.mcp.json` 파일 심링크)까지 생성한다.
- 버전 `0.1.0` 고정, doctor가 임의 부여하지 않음.

## doctor 검사 항목

1. **매니페스트 검증**: JSON 유효성 + `$schema` + 필수 필드(name/version/description) + name 일관성 (marketplace.json 최상위 name=마켓 이름은 제외). hermes는 YAML `plugin.yaml`을 stdlib 키 추출로 검증(PyYAML 의존 없음). grok 카탈로그(`.grok-plugin/marketplace.json`)는 항목마다 source를 검사한다: remote는 40자리 hex sha + url, local은 존재하는 path. 부재는 WARN하지 않는다(create 미생성이 정상). 이 검증은 구조 검증일 뿐 실제 브라우저 표시와는 별개다: standalone self-catalog는 구조가 valid해도 브라우저가 미표시된다(1.0.13 실측). Codex 카탈로그(`.agents/plugins/marketplace.json`)는 local path가 `./`로 시작하고 레포 루트(`"."`/`"./"`)가 아니며 실제로 존재하는지, `policy`·`category`가 있는지를 검사한다. `.codex-plugin/marketplace.json`은 Codex가 읽지 않아 WARN. 카탈로그 name은 마켓 id라 플러그인 name과 대조하지 않는다. `.lsp.json`이 있으면 JSON 유효성만 검사(스키마 미문서화).
2. **호스트 발견 경로 = 폴더 심볼릭 링크**: `.claude/skills`·`.codex/skills`·`.hermes/skills` → `../skills`, `.claude/agents` → `../agents`, `.codex/agents` → `../.codex-plugin/agents`. 실제 디렉터리(복제본)가 있으면 WARN, `--fix`가 삭제 후 링크로 교체. codex TOML ↔ 루트 md 커버리지도 검사.
2c. **MCP 배선**: 루트 `mcp_config.json`이 있으면 JSON 유효성 + claude·codex 매니페스트 선언을 검사하고 `--fix`가 배선한다. 구버전(`.mcp.json` + codex 심링크) 배선은 WARN하고 `--fix`가 자동 마이그레이션. 루트 `mcp.json`은 FAIL(어느 호스트도 읽지 않음).
3. **구조 일관성**: claude 매니페스트의 `skills`(디렉터리)/`commands`(디렉터리)/`agents`(파일 배열)/`mcpServers`(파일) 경로가 플러그인 루트 기준으로 실제 존재하는지 확인. 선언됐지만 없는 경로는 FAIL.
4. **라이프사이클 훅**: 호스트마다 경로·스키마·이벤트가 달라 교차 오염이 잘 생기는 지점을 검사한다.
   - 공용 `hooks/hooks.json`: grok 미선택 → FAIL (claude·codex **양쪽의 기본값**이라 어느 쪽이 집을지 불확실). grok 선택 → grok 스펙 위치라 WARN으로 누그러뜨림(단 claude/codex도 훅을 쓰면 매니페스트에 경로 명시 강력 권장) + JSON 유효성만 검사(xAI가 이벤트 스키마를 문서화하지 않아 이름 대조 불가)
   - 매니페스트가 선언한 훅 경로가 실제로 존재하는지 (매니페스트 경로는 **플러그인 루트 기준**이라 `"hooks.json"`은 agy 파일로 해석됨 → FAIL)
   - 호스트가 지원하지 않는 이벤트 → FAIL (codex엔 `Notification` 없음, agy는 5개 이벤트뿐)
   - agy 훅은 **named group**(`{"<이름>": {...}}`), claude/codex는 `{"hooks": {...}}` 구조인지
   - hermes `__init__.py`의 `register_hook` 이름이 `VALID_HOOKS`에 있는지 (오타는 런타임에 조용히 무시됨 → WARN)
4c. **커맨드 얇음 검사**: `commands/*.md` 본문(frontmatter 제외)이 8줄 초과 → WARN(스킬 내용 복제 신호), "skill" 미언급 → WARN(자체 지침을 든 커맨드). `README.md`는 예외. 위 "커맨드 정책" 참조.
5. **설치 dry-run**: 각 호스트 매니페스트 발견 가능성 (로컬 구조만, CLI 미실행).
6. **리모트 동기화**: `--owner` / `PLUGIN_FORGE_OWNER` / git origin이 있으면 `gh api`로 그 계정 아래 repo 존재 여부. 허브 등록 검사는 `--marketplace OWNER/REPO` 또는 `PLUGIN_FORGE_MARKETPLACE`가 있을 때만. 둘 다 없으면 건너뛴다.

## 호스트별 훅 파일 배치

| 호스트 | 훅 파일 | 비고 |
|--------|---------|------|
| claude | `.claude-plugin/hooks.json` | 매니페스트 `hooks`로 선언 |
| codex | `.codex-plugin/hooks.json` | 매니페스트 `hooks`로 선언. `Notification` 없음 → `PermissionRequest` |
| agy | `hooks.json` (루트) | **강제** — agy 매니페스트 스키마가 `additionalProperties:false`라 경로 선언 불가 |
| grok | `hooks/hooks.json` | grok 스펙 위치. claude/codex 기본값과 겹치므로 doctor가 grok 선택 여부로 구분 |
| hermes | *(파일 없음)* — `__init__.py`의 `ctx.register_hook(name, fn)` | 프로그래밍 방식 등록. 핸들러는 `fn(**kwargs)`로 호출됨 |

hermes는 훅이 **있다**(23개 `VALID_HOOKS`, `pre_approval_request`/`post_approval_response` 포함 — 5호스트 중 승인 이벤트가 1급으로 있는 유일한 호스트). 다만 잘못된 이름을 등록하면 hermes는 **로그 경고만 하고 조용히 무시**하므로 doctor가 이름을 대조한다. 실제 플러그인들은 이름을 컬렉션(`EVENTS`/`HOOK_STATES`)에 담아 넘기므로 리터럴 인자 매칭으로는 잡히지 않는다 — doctor는 파일 내 훅 형태 문자열을 휴리스틱으로 검사하고, 판정 불가면 INFO로 알린다.

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

plugin-forge 자신도 5호스트 구조로 만들어졌다. `forge.py doctor`를 자기 자신과
toefl-prep에 돌려 검증 기준이 맞는지 확인한다 (둘 다 0 FAIL 통과).

plugin-forge의 자기 `.grok-plugin/marketplace.json`은 remote url+sha 소스로
본 레포 HEAD를 핀한다(릴리스마다 재핀 필요). 표시 실측 완료: local `"."`
자기참조는 미표시(1.0.13, plugin_count=0), remote url+sha 전환 후
plugin_count=1. standalone url 핀 카탈로그도 유효한 배포 경로로 확인됐으며,
허브 sha 핀 등록(`publish --marketplace`)과 direct install이 병행 기준이다.
참고: `catalog_loaded=true`는 plugin-index.json 리치 카탈로그 기준 플래그라
standalone 카탈로그의 `false`는 정상이다.
