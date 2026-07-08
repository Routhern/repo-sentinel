# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

repo-sentinel는 PC 전역에 흩어진 git 저장소(GitHub, Gitee 등)를 중앙 목록화하고,
변경 사항을 감지하며, dotenv·개인 파일(`내_일기.md`)·중간 산출물 같은 민감한 데이터를
저장소 밖의 동기화 대상(시놀로지 NAS 등)을 통해 macOS/Windows 간 공유하기 위한
파이썬 CLI 도구입니다. CLI 기능을 그대로 재사용하는 GUI가 이후 추가될 예정입니다.
기획 배경 전문은 `CONTEXTS_AND_PLAN.md`에 있습니다.

**핵심 원칙**: 이 저장소 자체는 순수 소스코드만으로 구성되어야 하며 데이터나 시크릿을
포함하지 않는다. 사용자별 데이터(레지스트리, 설정)는 항상 저장소 바깥
`~/.repo-sentinel/`에 저장한다 (`core/config.py`의 `CONFIG_DIR`/`REGISTRY_FILE` 참고).
새 기능을 추가할 때 이 경계를 절대 넘지 말 것 — 어떤 사용자 데이터도 저장소 트리
안에 쓰면 안 된다.

## 개발 명령어

의존성 관리는 [uv](https://docs.astral.sh/uv/)를 사용한다.

```bash
uv sync                          # 의존성 설치 (.venv 생성)
uv run repo-sentinel --help      # CLI 실행
uv run repo-sentinel scan .      # 지정 경로 이하 git 저장소 스캔 후 레지스트리 등록
uv run repo-sentinel list        # 등록된 저장소 목록 출력
uv run repo-sentinel status      # 등록된 저장소들의 git dirty/clean 상태 출력

uv run pytest                    # 전체 테스트 실행
uv run pytest tests/test_scanner.py -q          # 단일 파일
uv run pytest tests/test_scanner.py::test_finds_git_repo  # 단일 테스트

uv add <package>                 # 런타임 의존성 추가
uv add --dev <package>           # 개발 의존성 추가
```

저장소를 어디로 옮기거나 다른 PC에 클론해도 그대로 동작해야 한다는 요구사항 때문에
`bin/repo-sentinel`(bash)과 `bin/repo-sentinel.cmd`(cmd)가 존재한다. 둘 다 저장소
루트로 이동한 뒤 `uv run repo-sentinel`을 위임 실행하는 얇은 래퍼일 뿐이며, uv 외의
사전 설치를 요구하지 않는다.

## 아키텍처

`src/` 레이아웃의 파이썬 패키지(`repo_sentinel`)이며, Typer 기반 CLI다.

- `cli.py` — Typer 앱과 서브커맨드(`scan`, `list`, `status`, `sync`) 정의. 커맨드 함수는
  얇게 유지하고 실제 로직은 `core/`에 위임한다.
- `core/config.py` — 사용자별 설정/레지스트리 파일 위치(`~/.repo-sentinel/`)를 정의하는
  단일 지점. 다른 모듈이 경로를 하드코딩하지 않고 항상 여기를 통해 참조한다.
- `core/scanner.py` — 파일시스템을 재귀 탐색해 `.git` 디렉터리를 가진 저장소를 찾는다.
  저장소를 찾으면 그 안쪽은 더 내려가지 않는다(서브모듈 제외). `.venv`, `node_modules`
  등은 애초에 재귀 대상에서 제외한다.
- `core/registry.py` — 스캔 결과를 `~/.repo-sentinel/registry.json`에 영속화한다.
  `merge_scanned_paths`는 재스캔 시 기존에 기록된 메타데이터(예: `remote_url`)를
  덮어쓰지 않고 보존한다.
- `core/sync.py` — dotenv/개인 파일 동기화 영역. `find_sensitive_files`만 구현되어
  있고, 실제 NAS/원격 전송(`push_to_sync_target`/`pull_from_sync_target`)은 전송
  프로토콜이 아직 정해지지 않아 `NotImplementedError` 스텁 상태다. 이 부분을 구현할
  때는 전송 대상이 macOS/Windows 양쪽에서 동일하게 마운트/접근 가능해야 한다는
  제약을 고려할 것.
- `gui/` — 아직 비어 있는 자리 표시자. GUI를 만들 때는 새 로직을 만들지 말고
  `core/`의 함수를 그대로 호출(포크)하도록 한다 — CLI와 GUI가 같은 로직을 공유해야
  한다는 것이 기획 의도다.
