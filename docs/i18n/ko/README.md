# plugin-forge

[English](../../../README.md) | **한국어**

<!-- 번역 원본: README.md (영문이 권위 있는 원본이며 더 최신일 수 있습니다) -->

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../../LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![플랫폼](https://img.shields.io/badge/플랫폼-Windows%20%7C%20Linux%20%7C%20macOS-6C757D.svg)](#사용법)
[![버전](https://img.shields.io/badge/버전-0.1.0-orange.svg)](../../../CHANGELOG.md)
[![지원 호스트](https://img.shields.io/badge/호스트-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20agy-7C3AED.svg)](#매니페스트-패턴-toefl-prep--byoh)
[![의존성 없음](https://img.shields.io/badge/의존성-표준%20라이브러리%20only-2EA44F.svg)](#사용법)
[![PR 환영](https://img.shields.io/badge/PR-환영-FF69B4.svg)](../../../CONTRIBUTING.md)

> 멀티호스트 플러그인 매니저 — **Claude Code · Codex · agy**. 하나의 엔진에서 플러그인을 생성·점검·설치 검증·배포합니다.

[toefl-prep](https://github.com/epicsagas/toefl-prep)와 byoh에서 매니페스트를 수작업으로 관리하던 경험에서 시작되었습니다. 모든 플러그인은 5개 이상의 매니페스트가 필요합니다 (agy용 루트 `plugin.json`, Claude용 `.claude-plugin/{plugin,marketplace}.json`, Codex용 `.codex-plugin/plugin.json`, 그리고 호스트 발견용 SKILL 복사본). plugin-forge가 이를 생성·검증하고, 로컬 설치 가능성을 점검하며, GitHub와 마켓플레이스로 배포합니다.

## 명령어

| 서브커맨드 | 기능 |
|------------|------|
| `create <name> [--hosts ...]` | 선택한 호스트의 매니페스트 + SKILL + 발견 복사본을 갖춘 새 플러그인 생성 |
| `doctor [PATH] [--fix]` | 매니페스트 검증, 호스트 복사본 동기화, 구조 점검, 설치 드라이런, 원격 동기화 |
| `install <PATH> [--host ...]` | 호스트별 로컬 설치 가능성 검증 (스테이징 + 롤백) |
| `publish [PATH] [--marketplace]` | git init + gh repo create + push + tag + 마켓플레이스 등록 |

## 설치

```bash
# Claude Code
claude plugin marketplace add epicsagas/plugins
claude plugin install epicsagas@plugin-forge

# Codex
codex plugin marketplace add epicsagas/plugins
codex plugin add epicsagas@plugin-forge

# agy (저장소 URL, .git 제외)
agy plugin install https://github.com/epicsagas/plugin-forge
agy plugin enable plugin-forge
```

## 사용법

크로스플랫폼: Windows / Linux / macOS에서 Python 3.8+면 어디서든 동작합니다. 표준 라이브러리만 사용합니다 (pip 설치 불필요).

```bash
# 3호스트 플러그인 생성
python3 scripts/forge.py create my-plugin --hosts claude,codex,agy --desc "Does X"

# 점검 (매니페스트, 동기화, 설치 드라이런, 원격)
python3 scripts/forge.py doctor my-plugin/

# 로컬 설치 가능성 검증
python3 scripts/forge.py install my-plugin/ --host all

# 배포 + 스위트 마켓플레이스 등록
python3 scripts/forge.py publish my-plugin/ --marketplace
```

> Windows에서는 `python3` 대신 `py` 또는 `python`을 사용하세요. bash가 필요하지 않습니다.

## 매니페스트 패턴 (toefl-prep / byoh)

| 파일 | 호스트 |
|------|--------|
| `plugin.json` (루트) | agy |
| `.claude-plugin/plugin.json` | Claude Code |
| `.claude-plugin/marketplace.json` | Claude 마켓플레이스 |
| `.codex-plugin/plugin.json` | Codex |
| `.claude/skills/<n>/`, `.codex/skills/<n>/` | 발견용 복사본 |

## 정직한 한계

- doctor/install은 **드라이런**입니다 — 로컬 구조를 검증하며, 실제 호스트 CLI 로드까지는 검증하지 않습니다.
- publish는 기존 원격 저장소를 덮어쓰지 않습니다.
- 버전은 생성 시점에 고정됩니다 (0.1.0); doctor/publish가 임의로 버전을 만들지 않습니다.

## 업데이트

`plugin-forge` 자체는 생성 시점에 버전이 고정됩니다 (현재 `0.1.0`). 최신 버전을 받으려면:

```bash
# Claude Code
claude plugin update plugin-forge

# Codex
codex plugin update plugin-forge

# agy — 최신 원격에서 재설치
agy plugin install https://github.com/epicsagas/plugin-forge
agy plugin enable plugin-forge
```

버전 확인:

```bash
python3 scripts/forge.py --version
```

릴리스 간 변경사항은 [CHANGELOG.md](../../../CHANGELOG.md)를 참고하세요.

## 커뮤니티

- 📋 [기여하기](../../../CONTRIBUTING.md)
- 🛡️ [보안 정책](../../../SECURITY.md)
- 💬 [지원 / 도움말](../../../SUPPORT.md)
- 📜 [행동 강령](../../../CODE_OF_CONDUCT.md)

## 라이선스

MIT
