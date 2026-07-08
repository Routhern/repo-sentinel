# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

repo-sentinel는 PC 전역에 흩어진 git 저장소(GitHub, Gitee 등)를 중앙 목록화하고,
변경 사항을 감지하며, dotenv·개인 파일(`내_일기.md`)·중간 산출물 같은 민감한 데이터를
저장소 밖의 동기화 대상(시놀로지 NAS 등)을 통해 macOS/Windows 간 공유하기 위한
파이썬 CLI 도구입니다. GUI 계획은 철회되었고, 대신 `core/`의 로직을 그대로
재사용하는 Textual 기반 TUI 대시보드(`repo-sentinel tui`)로 대체되었다.
기획 배경 전문은 `CONTEXTS_AND_PLAN.md`에, 버전별 변경 이력은 `CHANGELOG.md`에
있습니다.

**핵심 원칙**: 이 저장소 자체는 순수 소스코드만으로 구성되어야 하며 데이터나 시크릿을
포함하지 않는다. 사용자별 데이터(추적 목록, 설정)는 항상 저장소 바깥
`~/.repo-sentinel/`에 저장한다 (`core/config.py`의 `CONFIG_DIR` 참고).
새 기능을 추가할 때 이 경계를 절대 넘지 말 것 — 어떤 사용자 데이터도 저장소 트리
안에 쓰면 안 된다.

**사용자 관찰 가능한 변경**(신규 명령어, 동작 변경, 버그 수정 등)을 만들면
`CHANGELOG.md`의 `Unreleased` 항목에 함께 기록할 것.

## 개발 명령어

의존성 관리는 [uv](https://docs.astral.sh/uv/)를 사용한다. 전체 CLI 명령어와
옵션은 `docs/commands.md`에 정리되어 있고, 아래는 개발 중 자주 쓰는 것만 모은
치트시트다.

```bash
uv sync                          # 의존성 설치 (.venv 생성)
uv run repo-sentinel --help      # CLI 실행

uv run repo-sentinel scan .                    # git 저장소 탐색 (읽기 전용, 등록 안 함)
uv run repo-sentinel track <경로>               # 탐색된 저장소를 추적 대상으로 등록 (단축: t)
uv run repo-sentinel track <경로> --key <별칭>   # repo_key로 기본값 대신 짧은 별칭 사용 (-k)
uv run repo-sentinel untrack <repo_key>         # 추적 해제 (--mode restore|keep|purge) (단축: ut)
uv run repo-sentinel list                       # 추적 목록 출력
uv run repo-sentinel status                     # 추적 중인 저장소들의 git dirty/clean 상태

uv run repo-sentinel pick <repo_key> <상대경로...>      # 파일을 vault로 격리 + 심볼릭 링크 생성 (단축: p)
uv run repo-sentinel pick <repo_key> --auto             # sensitive_patterns로 후보 자동 탐색 후 격리
uv run repo-sentinel relink [repo_key]                  # 현재 머신 기준으로 심볼릭 링크 재생성
uv run repo-sentinel audit [repo_key]                   # 깨진 링크/gitignore 미반영/드리프트 점검
uv run repo-sentinel sync --direction push|pull         # vault_root <-> sync_target 미러링

uv run repo-sentinel set-vault-root <경로>       # vault_root 설정 (기본: ~/.repo-sentinel/vault)
uv run repo-sentinel set-sync-target <경로>      # NAS 등 동기화 대상 로컬 폴더 설정

uv run repo-sentinel tui                         # 추적 대시보드 TUI 실행

uv run pytest                                    # 전체 테스트 실행
uv run pytest tests/test_protect.py -q           # 단일 파일
uv run pytest tests/test_protect.py::test_protect_file_moves_and_links  # 단일 테스트
uv run pytest tests/test_tui_app.py -q           # TUI 헤드리스 스모크 테스트(Textual App.run_test)

uv add <package>                 # 런타임 의존성 추가
uv add --dev <package>           # 개발 의존성 추가
```

저장소를 어디로 옮기거나 다른 PC에 클론해도 그대로 동작해야 한다는 요구사항 때문에
`bin/repo-sentinel`(bash)과 `bin/repo-sentinel.cmd`(cmd)가 존재한다. 둘 다 저장소
루트로 이동한 뒤 `uv run repo-sentinel`을 위임 실행하는 얇은 래퍼일 뿐이며, uv 외의
사전 설치를 요구하지 않는다.

**Windows에서 `pick`/`relink` 테스트 시 주의**: 심볼릭 링크 생성은 Windows에서
개발자 모드(설정 > 업데이트 및 보안 > 개발자용) 또는 관리자 권한이 필요하다. 없으면
`SymlinkPermissionError`가 발생하며, 이 경우 `pick`은 vault로 옮겼던 파일을
원래 자리로 롤백한다. `tests/conftest.py`의 `symlinks_supported` 픽스처가 이 권한
유무를 감지해 관련 테스트를 자동으로 skip한다.

## 아키텍처 요약

`src/` 레이아웃의 파이썬 패키지(`repo_sentinel`)이며, Typer 기반 CLI다. 전체
데이터 흐름과 설계 배경은 `docs/architecture.md`에 있으니 새 기능을 설계하기
전에 먼저 읽을 것. 아래는 절대 어겨서는 안 되는 핵심 불변식만 요약한다.

- **repo-sentinel**은 정책 엔진, **NAS**는 단순 저장소다. 기준 상태는 항상 로컬
  `vault_root`이며, 레포를 NAS 경로에 직접 심볼릭 링크하지 않는다(마운트
  해제 시 링크가 깨진다). `vault_root` ↔ `sync_target` 미러링만 `sync`가
  담당하고, 여러 머신 간 `sync_target` 동기화 자체는 NAS/동기화 클라이언트의
  몫이지 repo-sentinel의 몫이 아니다.
- `repo_key`(`core/repo_key.py`)는 로컬 경로가 아니라 remote URL 기반이라 다른
  머신에서도 같은 키로 vault 매니페스트를 매칭할 수 있다. `vault_root/manifest.json`
  은 **vault_root 안에** 저장한다 — 설정 디렉터리에 두면 NAS로 동기화되지 않아
  새 머신에서 `relink`로 복구할 수 없다.
- CLI(`cli.py`)와 TUI(`tui/screens.py`)는 항상 `core/`의 같은 함수를 호출한다.
  정책 로직(무엇을 격리할지, 어떻게 복원할지 등)은 반드시 `core/`에만 두고
  CLI/TUI 양쪽에 중복 구현하지 않는다. `track`/`untrack`처럼 두 곳에서 거의
  동일하게 필요했던 로직은 `core/tracking.py`의 `track_repo`/`untrack_repo`
  헬퍼로 뽑아 CLI·TUI가 그대로 호출한다.
- `pick`(`core/protect.py`의 `protect_file`)은 심볼릭 링크 생성이 실패하면
  이동했던 파일을 원래 자리로 롤백한다 — 안 그러면 파일이 vault에 갇히고
  레포에는 아무것도 남지 않는 상태가 된다. `relink_repo`는 링크 자리에 실제
  파일이 있으면(드리프트) 덮어쓰지 않고 `DriftError`로만 알린다.

TUI는 번호 메뉴 + 화면(Screen) 전환 방식이다(자유 입력형 커맨드 라인은
폐기됨). `MainMenuScreen`에서 숫자 키(`1`~`6`)나 방향키+Enter로
`TrackScreen`/`UntrackScreen`/`RelinkScreen`/`ManageScreen`/`PickScreen`/
`SettingsScreen`으로 이동하고, `Esc`로 돌아가며, `q`로 종료한다. 자세한 화면별
책임은 `docs/architecture.md`의 TUI 섹션을 보라.

TUI를 헤드리스로 테스트할 때는 Textual의 `App.run_test()`(`tests/test_tui_app.py`
참고)로 `pilot.press`/`pilot.click`을 이용해 실제 화면 전환과 위젯 상호작용을
그대로 재현하고, `tracking.TRACKED_FILE`과 `tui.screens.load_config`를
monkeypatch해서 실제 `~/.repo-sentinel/`을 건드리지 않게 격리한다.
