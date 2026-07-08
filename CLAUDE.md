# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

repo-sentinel는 PC 전역에 흩어진 git 저장소(GitHub, Gitee 등)를 중앙 목록화하고,
변경 사항을 감지하며, dotenv·개인 파일(`내_일기.md`)·중간 산출물 같은 민감한 데이터를
저장소 밖의 동기화 대상(시놀로지 NAS 등)을 통해 macOS/Windows 간 공유하기 위한
파이썬 CLI 도구입니다. GUI 계획은 철회되었고, 대신 `core/`의 로직을 그대로
재사용하는 Textual 기반 TUI 대시보드(`repo-sentinel tui`)로 대체되었다.
기획 배경 전문은 `CONTEXTS_AND_PLAN.md`에 있습니다.

**핵심 원칙**: 이 저장소 자체는 순수 소스코드만으로 구성되어야 하며 데이터나 시크릿을
포함하지 않는다. 사용자별 데이터(구독 목록, 설정)는 항상 저장소 바깥
`~/.repo-sentinel/`에 저장한다 (`core/config.py`의 `CONFIG_DIR` 참고).
새 기능을 추가할 때 이 경계를 절대 넘지 말 것 — 어떤 사용자 데이터도 저장소 트리
안에 쓰면 안 된다.

## 개발 명령어

의존성 관리는 [uv](https://docs.astral.sh/uv/)를 사용한다.

```bash
uv sync                          # 의존성 설치 (.venv 생성)
uv run repo-sentinel --help      # CLI 실행

uv run repo-sentinel scan .                    # git 저장소 탐색 (읽기 전용, 등록 안 함)
uv run repo-sentinel track <경로>               # 탐색된 저장소를 추적 대상으로 등록 (단축: t)
uv run repo-sentinel track <경로> --key <별칭>   # repo_key로 기본값 대신 짧은 별칭 사용 (-k)
uv run repo-sentinel untrack <repo_key>         # 추적 해제 (--mode restore|keep|purge) (단축: ut)
uv run repo-sentinel list                       # 구독 목록 출력
uv run repo-sentinel status                     # 구독 중인 저장소들의 git dirty/clean 상태

uv run repo-sentinel pick <repo_key> <상대경로...>      # 파일을 vault로 격리 + 심볼릭 링크 생성 (단축: p)
uv run repo-sentinel pick <repo_key> --auto             # sensitive_patterns로 후보 자동 탐색 후 격리
uv run repo-sentinel relink [repo_key]                  # 현재 머신 기준으로 심볼릭 링크 재생성
uv run repo-sentinel audit [repo_key]                   # 깨진 링크/gitignore 미반영/드리프트 점검
uv run repo-sentinel sync --direction push|pull         # vault_root <-> sync_target 미러링

uv run repo-sentinel set-vault-root <경로>       # vault_root 설정 (기본: ~/.repo-sentinel/vault)
uv run repo-sentinel set-sync-target <경로>      # NAS 등 동기화 대상 로컬 폴더 설정

uv run repo-sentinel tui                         # 구독 대시보드 TUI 실행

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

## 아키텍처

`src/` 레이아웃의 파이썬 패키지(`repo_sentinel`)이며, Typer 기반 CLI다.

### NAS와 repo-sentinel의 책임 분리 (설계의 핵심 전제)

- **repo-sentinel**은 정책 엔진이다: 어떤 파일을 격리할지 결정하고(`pick`),
  `.gitignore` 반영을 검사하고, 로컬 심볼릭 링크를 관리한다.
- **NAS(시놀로지 등)**는 단순 저장소다: 여러 기기 간 파일 동기화·백업·버전 관리만
  담당한다. repo-sentinel은 NAS를 신뢰하지 않으며, 기준 상태는 항상 로컬
  `vault_root`다.
- 레포를 NAS 경로에 직접 심볼릭 링크하지 않는다 — NAS가 마운트 해제되면 링크가
  깨지기 때문이다. 대신 각 머신은 자신의 로컬 `vault_root`만 바라보고,
  `vault_root` ↔ `sync_target`(NAS가 동기화하는 로컬 폴더) 사이의 거울 맞추기만
  `sync` 커맨드가 담당한다. `sync_target`이 여러 머신에서 동일한 내용을 갖도록
  만드는 것은 NAS/동기화 클라이언트(예: Synology Drive)의 역할이지 repo-sentinel의
  역할이 아니다.

### 핵심 개념과 데이터 흐름

1. `scan` (`core/scanner.py`) — PC 전역에서 `.git` 저장소를 찾는다. **읽기 전용**이며
   아무것도 저장하지 않는다. 저장소를 찾으면 그 안쪽(서브모듈 등)은 더 내려가지 않고,
   `.venv`/`node_modules`류는 애초에 재귀 대상에서 제외한다.
2. `track`/`untrack` (`core/subscriptions.py`) — 사용자가 명시적으로 고른
   레포만 추적 대상이 된다. 로컬 클론 경로(`path`)는 머신마다 다를 수 있으므로
   `~/.repo-sentinel/subscriptions.json`에 로컬로만 저장하고, 머신 간 이식 가능한
   식별자는 `repo_key`를 쓴다.
3. `repo_key` (`core/repo_key.py`) — `git remote get-url origin`을 정규화해
   `host__owner__repo` 형태로 만든다(예: `github.com__Routhern__repo-sentinel`).
   로컬 경로가 아니라 remote URL 기반이라 다른 머신에서도 동일한 키로 vault
   매니페스트를 매칭할 수 있다. remote가 없는 로컬 전용 레포는 폴더명으로 대체하되
   이식성이 없다는 경고를 사용자에게 보여준다. host에 포트 번호가 포함되면
   (`host:port`) 콜론이 그대로 남을 수 있는데, 이는 `core/vault.py`의
   `vault_dir_name`이 디렉터리 이름으로 쓰기 전에 별도로 sanitize하므로
   `repo_key` 자체는 원본 그대로 유지된다. 이 기본값은 host/owner/repo를 모두
   이어붙여 상당히 길어질 수 있으므로, `track --key <별칭>`(`-k`)으로 사용자가
   원하는 짧은 문자열을 직접 repo_key로 지정할 수 있다. 이 경우 이식성 책임은
   사용자에게 넘어간다 — 다른 머신에서도 반드시 같은 `--key`로 track해야 vault가
   같은 키로 매칭되어 `relink`가 동작한다.
4. `vault` (`core/vault.py`) — `vault_root/<repo_key>.repo-sentinel-vault/`에 실제
   파일을 보관하고, `vault_root/manifest.json`에 "어떤 레포의 어떤 상대경로가
   보호되어 있는지"를 기록한다. **매니페스트는 vault_root 안에 저장**한다 — 이것도
   NAS로 동기화되어야 새 머신에서 `relink`만으로 로컬 상태를 재구성할 수 있기
   때문이다(설정 디렉터리에 두면 동기화되지 않아 못 쓴다).
5. `gitignore` (`core/gitignore.py`) — `pick`이 만드는 심볼릭 링크는 vault의
   로컬 절대경로를 담고 있으므로, 레포의 `.gitignore`가 그 경로를 무시하지 않으면
   링크 파일 자체가 커밋되어 다른 머신에서 깨진 링크로 남는다. `is_ignored`로 검사만
   하고, 실제 `.gitignore` 수정(`add_entry`)은 CLI가 사용자 확인을 받은 뒤에만
   호출한다.
6. `protect`/`restore`/`relink` (`core/protect.py`) — 기준 상태는 vault다.
   - `protect_file`: 레포의 실제 파일을 vault로 이동하고 원래 자리에 심볼릭 링크를
     만든다. 심볼릭 링크 생성이 실패하면(Windows 권한 문제 등) **이동했던 파일을
     원래 자리로 롤백**한다 — 안 그러면 파일이 vault에 갇히고 레포에는 아무것도
     남지 않는 상태가 된다.
   - `restore_file`: vault의 실제 파일을 레포 쪽으로 되돌리고 링크를 제거한다.
     `delete_vault_copy` 여부로 vault 사본을 남길지 결정한다(untrack의
     restore/keep 모드가 이 차이를 사용한다).
   - `relink_repo`: 매니페스트 기준으로 현재 머신의 깨진/누락된 링크를 재생성한다.
     링크 자리에 진짜 파일이 있으면(드리프트) 덮어쓰지 않고 `DriftError`로만
     알린다 — 사용자 데이터를 실수로 지우지 않기 위함이다.
7. `audit` (`core/audit.py`) — 보호 중인 파일마다 깨진 링크, vault 파일 누실,
   드리프트, `.gitignore` 미반영을 점검해 `AuditIssue` 목록으로 보고한다.
8. `sync` (`core/sync.py`) — `vault_root`와 `sync_target` 두 로컬 디렉터리 트리만
   다루며 레포를 전혀 알지 못한다. mtime 기준 "최신 파일 우선"으로 한쪽에서
   다른 쪽으로 파일을 복사한다(`push`/`pull`). 표시용 상대경로는 OS와 무관하게
   항상 `/` 구분자(`Path.as_posix()`)로 반환한다.

### untrack의 세 가지 모드

`pick`된 파일이 있는 레포를 무작정 추적 해제하면 레포에 깨진 심볼릭 링크만
남는다. 그래서 `--mode`로 명시적으로 선택하게 한다:
- `restore`(기본값, 권장) — vault의 실제 파일을 레포로 복원하고 vault 사본은 삭제.
- `keep` — 구독만 해제, vault 데이터와 레포의 링크는 그대로 둔다(고아 상태로 보존).
- `purge` — vault 데이터를 즉시 삭제한다. 레포에 깨진 링크가 남을 수 있어 CLI에서
  반드시 확인(`typer.confirm`)을 받는다.

### TUI (`tui/`, Textual)

GUI 계획은 철회하고 Textual 기반 TUI로 대체했다. `tui/`도 `core/`의 함수를 그대로
호출할 뿐 새 정책 로직을 만들지 않는다 — CLI와 TUI가 같은 로직을 공유해야 한다는
원칙은 그대로 유지된다.

- `tui/app.py` — `RepoSentinelApp`(Textual `App`). 구독 목록을 `DataTable`로,
  명령 실행 결과를 `RichLog`로, 명령 입력을 `Input`으로 보여주는 단일 화면
  대시보드다. `on_input_submitted`가 입력을 토큰화(`shlex.split`)해서
  `track`/`untrack`/`pick`/`relink`/`audit`/`sync`/`refresh`/`quit`로
  분기하며, 각 핸들러는 CLI와 마찬가지로 `core/`를 직접 호출한다. CLI의
  `typer.confirm`(대화형 프롬프트)은 풀스크린 앱 안에서 쓸 수 없으므로, TUI의
  `pick`은 `.gitignore` 미반영을 발견하면 확인 없이 자동으로 추가하고 로그로
  알린다(사용자 확인이 필요하면 로그에서 바로 되돌릴 수 있는 수준의 변경이라
  안전하다고 판단).
- `tui/suggester.py` — 명령창 자동완성. 1번째 토큰은 명령어 접두 매칭, 2번째
  토큰은(해당 명령이 repo_key를 받는 경우) 구독 중인 repo_key 접두 매칭, `pick`의
  3번째 이후 토큰은 레포 내 상대경로 자동완성으로 이어진다. Textual의 `Input`은
  suggestion을 "현재 입력값의 리터럴 접두어 확장"으로 취급해 나머지를 고스트
  텍스트로 그리므로, 매칭은 반드시 **접두어 매칭**이어야 한다(부분 문자열 매칭을
  쓰면 고스트 텍스트가 깨진다). 순수 로직(`compute_suggestion`)은 Textual 의존 없이
  분리되어 있어 단위 테스트가 쉽다.
- `tui/paths.py` — `pick` 3번째 토큰용 경로 자동완성. 셸 탭 완성처럼 마지막
  `/` 기준으로 디렉터리를 열어 그 안의 항목을 접두 매칭한다. `Path(".").name`이
  빈 문자열로 접혀버리는 pathlib 특성 때문에 `Path`가 아니라 `str.rpartition("/")`로
  직접 구현한다.
- `tui/styles.tcss` — 의도적으로 표준 ANSI 8색(그리고 `text-style: bold`로 표현하는
  밝은 계열)만 사용한다. truecolor를 지원하지 않는 터미널(오래된 SSH 클라이언트 등)
  에서도 항상 동일하게 보이도록 하기 위함이며, 새 위젯을 추가할 때도 이 팔레트
  밖의 색을 쓰지 않는다.

TUI를 헤드리스로 테스트할 때는 Textual의 `App.run_test()`(`tests/test_tui_app.py`
참고)를 쓰고, `subscriptions.SUBSCRIPTIONS_FILE`과 `tui.app.load_config`를
monkeypatch해서 실제 `~/.repo-sentinel/`을 건드리지 않게 격리한다.
