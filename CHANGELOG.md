# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전 표기는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

### Security

- 조작된 `manifest.json`(NAS로 동기화되는 `vault_root` 안에 있음)이 `..`나
  절대 경로가 섞인 `relative_path`를 담고 있을 경우, `untrack --mode restore`가
  레포 밖의 임의 파일을 삭제하거나 `relink`가 레포 밖 임의 위치에 심볼릭
  링크를 생성할 수 있었던 경로 검증 누락을 수정했습니다. 이제
  `core/protect.py`의 `restore_file`/`relink_repo`는 `relative_path`가
  `repo_path`/`vault_root`를 벗어나면 각각 `UnsafeRelativePathError`를 던지거나
  (relink의 경우) 해당 항목만 건너뛰고 `DriftError`로 알립니다.
- `sync --direction pull`이 `sync_target`(NAS 등) 안의 심볼릭 링크를 따라가
  그 대상 파일/디렉터리 내용을 vault로 그대로 복사해 오던 문제를
  수정했습니다. `core/sync.py`의 `_mirror`가 이제 심볼릭 링크(파일·디렉터리
  모두)를 건너뛰어, 공유 NAS 폴더에 심긴 심볼릭 링크로 로컬의 임의 파일이
  vault에 유입되는 경로를 막습니다.

### Changed

- 레거시 `구독`/`subscribe` 명칭을 전면 정리했습니다: `core/subscriptions.py` →
  `core/tracking.py`, `Subscription` → `TrackedRepo`, `subscriptions.json` →
  `tracked.json`. 기존 설치는 `repo-sentinel list` 등을 처음 실행할 때 필드명까지
  포함해 한 번만 자동으로 이관됩니다(데이터 손실 없음).
- `CLAUDE.md`의 아키텍처 설명을 [`docs/architecture.md`](docs/architecture.md)로
  이전하고, CLI 사용법은 [`docs/commands.md`](docs/commands.md)로 분리했습니다.
- TUI를 자유 입력형 커맨드 라인에서 번호 메뉴 + 화면(Screen) 전환 방식으로
  전면 재설계했습니다. 메인 메뉴(`1` Track / `2` Untrack / `3` Relink / `4`
  레포지토리 관리 / `5` Pick / `6` 환경설정 / `q` 종료)에서 각 화면으로
  이동하며, "레포지토리 관리" 화면은 추적 목록 표 + `Sync Push`/`Pull`
  버튼과, 레포를 선택하면 들어가는 상세 화면(감사 결과, Relink/Pick/Untrack
  바로가기)으로 구성됩니다. "환경설정" 화면에서 `vault_root`/`sync_target`/
  `sensitive_patterns`를 폼으로 편집할 수 있는 기능도 새로 생겼습니다.
  `untrack`의 `purge` 모드는 실행 전에 확인 대화상자를 거칩니다.
- CLI의 `track`/`untrack` 명령이 새로 만든 `core.tracking.track_repo`/
  `untrack_repo` 헬퍼를 호출하도록 정리해, TUI와 완전히 같은 정책 로직을
  공유하도록 했습니다.

### Added

- `track`이 레포의 `.gitignore`에 repo-sentinel 리전(`# >>> repo-sentinel: pick
  후보 패턴 >>>` ~ `# <<< ... <<<`)을 확인/생성하고, 그 리전의 패턴에
  매칭되는 pick 후보가 있으면 하나씩 지금 pick할지 물어보는 기능을
  추가했습니다. 리전이 이미 있으면 절대 덮어쓰지 않습니다 — 패턴 갱신은
  사용자가 `.gitignore`의 그 구간을 직접 편집하는 수동 과정입니다. 리전이
  있는 레포에서는 `pick --auto`도 전역 `sensitive_patterns` 대신 이 리전의
  패턴을 우선 사용합니다(`core/gitignore.py`의 `ensure_region`/
  `read_region_patterns`/`resolve_patterns`, `core/tracking.py`의
  `track_repo`가 계산해 `TrackResult.pick_candidates`로 돌려줌).
- `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`(MIT), `docs/` 문서 카테고리를
  새로 도입했습니다.
- `bin/repo-sentinel-admin.vbs`를 추가했습니다. Windows에서 개발자 모드를 켤 수
  없을 때 별도 설치 없이 UAC 승인만으로 `repo-sentinel`을 관리자 권한으로
  실행합니다(인자를 생략하면 `tui`, 주면 그대로 CLI에 전달).

### Removed

- 자유 입력형 커맨드와 그 자동완성을 담당하던 `tui/suggester.py`를 번호
  메뉴 UI로 대체하면서 제거했습니다.

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
