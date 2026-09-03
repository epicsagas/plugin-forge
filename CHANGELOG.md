# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-09-03

### Fixed
- **`publish --marketplace`: grok 카탈로그 기존 엔트리의 `version` 갱신 추가.** sha 핀 갱신은 기존 기능이었으나 version은 새 엔트리에만 기록됐다. 이제 기존 엔트리도 sha·version을 함께 갱신한다.

### Changed
- **grok sha-pinning causes stale reinstall until hub catalog bump (운영 기록).** 허브 카탈로그의 sha는 설치 커밋을 고정하고 `grok plugin update`는 그 sha만 다시 받는다. 업스트림 push 후 `publish --marketplace`를 재실행하지 않으면 재설치가 영원히 구 커밋에 머문다. 재현: epic-harness가 561e206에 고정돼 수정 푸시 후에도 재설치가 구 버전을 받던 사례(수동 sha 갱신으로 해결). forge publish는 기존 엔트리의 sha·version을 자동 갱신한다.
- **grok 매니페스트 템플릿에 flat 경로 키 추가.** `plugin.json.grok.tpl`이 `"skills"`/`"commands"`/`"agents"` 경로 키와 `"hooks": "./hooks/hooks.json"` 문서 참조를 포함한다. 실측(1.0.13): `components` 객체는 완전 무시되고 flat 키만 유효하다.
- **doctor grok 검사 확충.** (a) 매니페스트 `components` 객체는 FAIL(무시됨 실측), (b) `.grok-plugin/hooks.json` 사본은 WARN(grok이 안 읽음, A/B 삭제 실측), (c) 매니페스트 hooks 키가 `./hooks/hooks.json` 외를 가리키면 WARN(키는 문서용이므로 실제 경로 가리켜야 정직), (d) `.claude-plugin/hooks.json`이 있는데 claude 매니페스트 `hooks` 필드가 없고 루트 훅 파일도 없으면 WARN(단독으로는 로드되지 않음), (e) `hooks/hooks.json` 커맨드에 `command -v`/`sh -c` 가드가 없으면 WARN(깨진 PATH에서 즉사 방지).

## [0.2.1] - 2026-09-03
- **grok standalone self-catalog 생성 중단.** `create`가 더 이상 `.grok-plugin/marketplace.json`(local source `"."`)을 생성하지 않는다. 실측(Grok Build 1.0.13): 자기참조 local `"."` 카탈로그는 마켓플레이스 브라우저에서 표시되지 않는다(standalone 리포 9개 전부 plugin_count=0, 허브 remote sha 핀 카탈로그는 plugin_count=7로 정상). grok 배포는 허브 sha 핀 등록(`publish --marketplace`) 또는 direct install(`grok plugin install owner/repo --trust`). 기존 플러그인의 카탈로그 파일은 유지된다.
- doctor가 `.grok-plugin/marketplace.json` 부재를 WARN하지 않는다(이제 정상 상태). 파일이 있으면 기존처럼 구조를 검증한다(remote 40자리 sha 핀, local path 존재). 이는 구조 검증이며 브라우저 표시를 보장하지 않는다.
- **plugin-forge 자기 카탈로그를 remote url+sha 소스로 전환.** `.grok-plugin/marketplace.json`의 엔트리가 local `"."`(브라우저 미표시 실측)에서 본 레포 HEAD sha 핀 remote 소스로 바뀌었고, 6개 자기 매니페스트의 `YOUR_GITHUB_USER` 플레이스홀더를 `epicsagas`로 교정했다. 카탈로그 sha는 릴리스마다 재핀해야 한다. 전환 후 실측으로 확정: standalone url+sha 카탈로그도 브라우저에 표시된다(plugin_count 0에서 1로 확인).
- doctor가 grok 카탈로그의 루트 local path(`"."`/`"./"`, 자기참조)를 WARN한다: 브라우저가 미표시(1.0.13 실측)이므로 remote url+sha 소스를 권장. 서브디렉터리 local 소스(xAI 공식 카탈로그 방식)는 기존대로 PASS.

## [0.2.1] - 2026-09-03

### Fixed
- **`publish --marketplace`: grok 카탈로그 생성 시 `name`이 임시 클론 디렉터리명(`mpl`)으로 기록되던 버그.** 허브 레포에서 유도(`OWNER/REPO`의 REPO)하도록 수정. `owner`도 허브 레포 기준으로 유도.
- **`publish --marketplace`: hermes 미대상 플러그인(루트 `plugin.yaml` 없음)도 허브에 `.hermes/<name>/plugin.yaml` 스텁이 생겨 hermes 설치가 실패하는 죽은 엔트리가 만들어지던 버그.** 플러그인 경로에 hermes 매니페스트가 있는지 확인 후 스텁 생성, 없으면 WARN과 함께 스킵. 기존 엔트리의 버전 갱신 경로는 유지.

### Changed
- `publish --marketplace`: grok 카탈로그 신규 엔트리의 `keywords`/`category`를 플러그인 `.grok-plugin/plugin.json` 값에서 우선 사용(없으면 기존대로 `[name]`/`development`).

## [0.2.0] - 2026-09-02

### Added
- **grok (xAI Grok Build) 호스트 지원.** 5호스트(claude/codex/agy/hermes/grok) 구조.
  - `create --hosts ...,grok`가 `.grok-plugin/plugin.json` 메타데이터 매니페스트를 생성한다. 컴포넌트(`skills/`·`commands/`·`agents/`)는 플러그인 루트에서 네이티브로 읽혀 발견용 심볼릭 링크가 필요 없다 ([xAI plugin-marketplace](https://github.com/xai-org/plugin-marketplace) 형식).
  - MCP: grok은 루트 `.mcp.json`을 읽는다 — `--mcp` 생성 시 `mcp_config.json`(agy 스펙 원천)으로 **파일 심볼릭 링크**. doctor는 grok 미선택 플러그인의 실제 `.mcp.json` 파일만 구배선(legacy)으로 WARN하고, grok 선택 시 심볼릭 링크를 검사·`--fix`한다(원천 없으면 실제 파일을 원천으로 채택 후 링크).
  - 훅: `hooks/hooks.json`은 grok 스펙 위치. grok 미선택 시 기존처럼 FAIL(claude/codex 공용 기본값), grok 선택 시 WARN + JSON 유효성 검사(xAI가 이벤트 스키마를 문서화하지 않아 이름 대조 생략). claude/codex 매니페스트가 grok 훅 파일을 가리키면 FAIL.
  - `create --hosts ...,grok`가 자체 `.grok-plugin/marketplace.json`도 깐다 (local source `"."`). Grok Build가 이 리포를 카탈로그로 추가할 수 있다.
  - `publish --marketplace`: 마켓 저장소의 `.grok-plugin/marketplace.json` 카탈로그에 sha 핀 원격 소스로 등록·갱신한다(푸시된 HEAD sha 필수 — 드라이런은 NEEDS_SHA로 스킵, Grok Build가 설치 시 `git rev-parse HEAD == sha` 재검증). 카탈로그 파일이 없으면 생성한다 (hermes `plugin.yaml`과 동일 — 없으면 `grok:MISSING`으로 조용히 빠지지 않음).
  - doctor가 grok 카탈로그 항목을 검사한다: remote는 40자리 hex sha + url, local은 존재하는 path. 카탈로그 name은 마켓 id라 플러그인 name과 대조하지 않는다. `.lsp.json`이 있으면 JSON 유효성만 검사(xAI가 스키마를 문서화하지 않음).
  - doctor/install에 grok 매니페스트 검증·이름 추론 추가. grok 설치 CLI는 공개되지 않아 추측 명령을 만들지 않는다(카탈로그 등록 경로만 안내).
- plugin-forge 자신이 5호스트 구조로 이행(`.grok-plugin/plugin.json` + 자체 `.grok-plugin/marketplace.json` 추가, 버전 0.2.0).
- **Codex 단독 마켓.** `create --hosts ...,codex`가 `.agents/plugins/marketplace.json`을 플러그인 안에 깐다 (`.codex-plugin/marketplace.json`이 아님). Codex가 거부하는 local path `"./"` 대신 `./plugins/<name>`을 쓰고, 그 경로는 루트 `.codex-plugin`·`skills` 등으로의 디링크다. doctor가 카탈로그를 검사하고 `--fix`가 빠진 파일·번들을 보충한다.
- **커맨드 얇음 검사(doctor).** `commands/*.md` 본문(frontmatter 제외)이 8줄을 넘거나 "skill"을 한 번도 언급하지 않으면 WARN. `commands/README.md`는 규칙 문서라 예외.
- `create`가 빈 `commands/.gitkeep` 대신 얇은 위임 규칙 + 템플릿을 담은 `commands/README.md`를 생성한다.

### Changed
- **GitHub owner / 허브 카탈로그 기본값 제거.** `PLUGIN_FORGE_OWNER`와 `PLUGIN_FORGE_MARKETPLACE`는 비어 있다. `--owner LOGIN` 또는 환경변수로 채운다. create는 비어 있으면 `YOUR_GITHUB_USER` 자리표시 + WARN, publish는 owner 없이 거부. `--marketplace`는 옵션 허브(`OWNER/REPO`)이며 생성 플러그인의 설치 안내는 그 플러그인 레포 자체다.
- **커맨드를 스킬 위임 스텁으로 축소.** `commands/plugin-forge-{create,doctor,install,publish}.md`가 각각 12줄로 줄었다(이전 30~40줄): frontmatter + "plugin-forge 스킬의 해당 액션을 `$ARGUMENTS`로 실행" 한 줄. 인자 문서·체크리스트·검증 범위·호스트 목록은 전부 `skills/plugin-forge/SKILL.md`로 이동.
  - **이유**: 커맨드가 스킬 내용을 복제하면 호스트 하나 추가할 때 5곳을 고쳐야 한다. 실제로 grok 추가 시 4개 커맨드 파일을 전부 수동 수정해야 했고, 그중 하나(`argument-hint`)는 놓쳐서 뒤늦게 잡았다. 이제 새 동작은 SKILL.md와 forge.py에만 추가하고 스텁은 건드리지 않는다.
- SKILL.md에 **커맨드 정책** 절 추가, 의도→액션 표를 `forge.py` 직접 호출로 통일(슬래시 명령을 액션 경로로 나열하지 않음). AGENTS.md·CONTRIBUTING.md에도 동일 규칙 반영.

## [0.1.9] - 2026-09-01

### Changed
- **MCP 단일 원천 파일명을 `mcp_config.json`으로 전환** (Antigravity 플러그인 스펙 파일명). `create --mcp`가 루트 `mcp_config.json`을 생성하고 claude·codex 매니페스트가 같은 파일을 가리킨다 (복사본·심볼릭 없음). agy는 루트 파일을 자동 발견하므로 배선 불필요. 구버전 배선(0.1.6~0.1.8의 루트 `.mcp.json` + codex `mcp_config.json` 심링크)은 doctor가 WARN하고 `--fix`가 자동 마이그레이션한다.

### Fixed
- doctor가 루트 `mcp.json`을 FAIL로 지적한다. 어느 호스트도 해당 이름을 읽지 않아 MCP 서버가 조용히 사라진다. `mcp_config.json`의 JSON 유효성도 검사한다.

## [0.1.8] - 2026-08-20

### Docs
- hermes install blocks (README here + the scaffold template) now mention the
  skills_guard escape hatch: `plugins.scan_on_install: false`.

## [0.1.7] - 2026-08-20

### Fixed
- **`create --dir` now creates `<dir>/<name>/`.** Previously the plugin files
  were written directly into `--dir` itself, polluting e.g. a workspace root
  (and the post-create listing then walked every sibling repo under it).
- Unknown-host error message now lists all four hosts (was `claude|codex|agy`).

### Added
- **doctor: hermes install pre-scan.** hermes' `skills_guard` flags any file
  mentioning `AGENTS.md` / `CLAUDE.md` / `.cursorrules` / `.clinerules` (even a
  README link) as CRITICAL persistence, and community source + dangerous then
  hard-blocks `hermes plugins install` with no `--force` escape. doctor now
  WARNs about the offending files before publish (escape hint:
  `plugins.scan_on_install: false`).

## [0.1.6] - 2026-08-20

### Added
- **MCP single-source wiring.** Root `.mcp.json` is the only MCP config:
  `create --mcp` scaffolds it plus per-host wiring, and `doctor` enforces it —
  claude's manifest must declare `mcpServers: ["./.mcp.json"]`, codex's
  `mcp_config.json` must be a file symlink to `.mcp.json` (same
  `{"mcpServers": {...}}` shape as BYOH/gamestudio). `--fix` wires both.
  agy auto-discovers the root file; hermes has no file-based MCP convention.

## [0.1.5] - 2026-08-20

### Changed
- **Host-discovery paths are now FOLDER symlinks.** `create` links `.claude/skills`,
  `.codex/skills`, `.hermes/skills` → `../skills` and `.claude/agents` → `../agents`
  as whole-directory symlinks instead of per-file `SKILL.md` links. A skill added under
  root `skills/` now appears in every host automatically; per-host copies (the recurring
  duplication bug) are gone.
- **Codex agents must be Codex-native TOML.** Root `agents/<n>.md` is never linked for
  Codex — each agent is rewritten as `.codex-plugin/agents/<n>.toml`
  (`name` / `description` / `developer_instructions`), and `.codex/agents` links that folder.
- `doctor` rewritten accordingly: real directories where a dir symlink belongs are WARN
  (with the duplicated file count) and `--fix` replaces them with the link; md↔toml agent
  coverage is checked both ways (missing TOML twin / orphan TOML).
- `publish --marketplace` now refreshes the hermes `plugin.yaml` version in the
  marketplace repo when it drifts. Previously it only appended new entries, so a release
  never bumped the one marketplace manifest that carries a version.
- SKILL.md contradiction removed ("복사본 기본" said real copies while forge.py linked —
  hand-generation sessions followed the prose and duplicated skills).

## [0.1.3] - 2026-07-20

### Added
- **hermes (Nous Research) host support** — 4th target host alongside claude/codex/agy.
  - New `plugin.yaml` YAML manifest template (`scripts/templates/plugin.yaml.hermes.tpl`) at the plugin root, plus an `__init__.py` stub with `register(ctx)` (required by the [Hermes plugin spec](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)).
  - `create --hosts ...,hermes` scaffolds the YAML manifest, `__init__.py`, and `.hermes/skills/<n>/` discovery symlink.
  - `doctor` validates the YAML manifest via stdlib-only key extraction (no PyYAML dependency) and checks `.hermes/` discovery sync.
  - `install --host hermes` stages into `~/.hermes/plugins/forge-validate-<name>/` and verifies `plugin.yaml` + `__init__.py`.
  - `publish` prints the `hermes plugins install` / `enable` commands.

### Changed
- `VALID_HOSTS` now includes `hermes`; `--hosts` default is `claude,codex,agy,hermes`.

## [0.1.2] - 2026-07-15

### Fixed
- `doctor` step-3 structure check now validates `agents` (array of file paths) and `mcpServers` (file) relative to the plugin root, and FAILs on a declared-but-missing path instead of silently skipping it. Correctly-structured plugins (e.g. byoh) are no longer falsely flagged as broken. (Fixes #3)

## [0.1.1] - 2026-07-15

### Added
- `--version` flag on `forge.py` to print the engine version.
- Community files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`.
- Multilingual README structure under `docs/i18n/<lang>/`.
- Issue and pull request templates.

### Fixed
- Fixed variable shadowing in `scripts/forge.py` `doctor` command that bypassed Claude plugin structure consistency checks.
- Track `.codex` host-discovery copy (was blocked by global gitignore).

### Changed
- Ported engine from `forge.sh` to `forge.py` (cross-platform, standard library only).

## [0.1.0] - 2026-07-15

### Added
- `create <name> [--hosts ...]` — scaffold a plugin with selected hosts' manifests, SKILL, and discovery copies.
- `doctor [PATH] [--fix]` — validate manifests, sync host copies, structure check, install dry-run, remote sync.
- `install <PATH> [--host ...]` — validate local installability per host (staging + rollback).
- `publish [PATH] [--marketplace]` — git init + `gh repo create` + push + tag + marketplace registration.
- Cross-platform engine ported from `forge.sh` to `forge.py` (standard library only).
- Multi-host manifest pattern: root `plugin.json` (agy), `.claude-plugin/` (Claude), `.codex-plugin/` (Codex), host-discovery SKILL copies.

[Unreleased]: https://github.com/YOUR_GITHUB_USER/plugin-forge/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/YOUR_GITHUB_USER/plugin-forge/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/YOUR_GITHUB_USER/plugin-forge/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/YOUR_GITHUB_USER/plugin-forge/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/YOUR_GITHUB_USER/plugin-forge/releases/tag/v0.1.0
