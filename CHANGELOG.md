# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전 표기는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

### Changed

- 레거시 `구독`/`subscribe` 명칭을 전면 정리했습니다: `core/subscriptions.py` →
  `core/tracking.py`, `Subscription` → `TrackedRepo`, `subscriptions.json` →
  `tracked.json`. 기존 설치는 `repo-sentinel list` 등을 처음 실행할 때 필드명까지
  포함해 한 번만 자동으로 이관됩니다(데이터 손실 없음).
- `CLAUDE.md`의 아키텍처 설명을 [`docs/architecture.md`](docs/architecture.md)로
  이전하고, CLI 사용법은 [`docs/commands.md`](docs/commands.md)로 분리했습니다.

### Added

- `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`(MIT), `docs/` 문서 카테고리를
  새로 도입했습니다.

## [0.1.0] - 2026-07-08

### Added

- uv/Typer 기반 CLI 스캐폴딩과 크로스플랫폼 실행 래퍼(`bin/repo-sentinel`,
  `bin/repo-sentinel.cmd`)를 부트스트랩했습니다.
- `scan`(읽기 전용 탐색), `track`/`untrack`(구독 관리), `pick`(민감 파일 vault
  격리 + 심볼릭 링크), `relink`(머신별 링크 재생성), `audit`(무결성 점검),
  `sync`(vault_root ↔ sync_target 미러링)로 구성된 vault 아키텍처를
  도입했습니다.
- 명령 자동완성과 경로 완성을 지원하는 Textual 기반 TUI 대시보드
  (`repo-sentinel tui`)를 추가했습니다.
- `track`/`untrack`/`pick` 각각에 단축 별칭 `t`/`ut`/`p`를 추가하고, 기존
  `subscribe`/`unsubscribe`/`protect` 명칭을 새 이름으로 전면 변경했습니다.
- `track --key`/`-k` 옵션으로 remote URL 기반의 긴 기본 repo_key 대신 사용자
  지정 별칭을 쓸 수 있게 했습니다. 이미 다른 경로가 같은 키를 쓰고 있으면
  등록을 거부해 조용한 데이터 덮어쓰기를 방지합니다.

### Fixed

- host에 포트 번호가 포함된 remote URL(`host:port` 형태)의 repo_key가 Windows
  경로에 쓸 수 없는 콜론(`:`)을 그대로 포함해 `pick` 시 vault 디렉터리 생성이
  실패하던 문제를 수정했습니다. `repo_key` 자체는 그대로 유지하고, vault
  디렉터리 이름으로 변환할 때만 안전하게 치환합니다.
