# CLI 명령어 참고

의존성 관리는 [uv](https://docs.astral.sh/uv/)를 사용한다.

```bash
uv sync                          # 의존성 설치 (.venv 생성)
uv run repo-sentinel --help      # CLI 실행
```

## 탐색 · 추적

| 명령 | 단축 | 설명 |
| --- | --- | --- |
| `scan [경로]` | | `.git` 저장소를 찾아 보여준다 (읽기 전용, 아무것도 등록하지 않는다). |
| `track <경로> [--key/-k 별칭]` | `t` | 저장소를 추적 대상으로 등록한다. `--key`를 생략하면 remote URL 기반의 긴 `repo_key`가 자동 계산된다. |
| `untrack <repo_key> [--mode restore\|keep\|purge]` | `ut` | 추적을 해제한다. 기본값은 `restore`. |
| `list` | | 추적 중인 저장소 목록을 출력한다. |
| `status` | | 추적 중인 각 저장소의 git dirty/clean 상태를 요약한다. |

### `track --key`로 짧은 repo_key 쓰기

기본 `repo_key`는 `host__owner__repo`를 그대로 이어붙이므로 host에 포트
번호가 있으면(`git.example.com:32768__me__repo`) 상당히 길어질 수 있다.
`--key`/`-k`로 원하는 짧은 별칭을 직접 지정할 수 있다:

```bash
uv run repo-sentinel track D:\Gitea\myFirstRepo --key myrepo
```

이 경우 이식성 책임은 사용자에게 넘어간다 — **다른 머신에서도 반드시 같은
`--key`로 track**해야 vault가 같은 키로 매칭되어 `relink`가 동작한다. 이미
다른 경로가 같은 키를 쓰고 있으면 등록이 거부된다.

### `untrack`의 세 가지 모드

`pick`된 파일이 있는 레포를 무작정 추적 해제하면 레포에 깨진 심볼릭 링크만
남으므로 `--mode`로 명시적으로 선택한다:

- `restore`(기본값, 권장) — vault의 실제 파일을 레포로 복원하고 vault
  사본은 삭제.
- `keep` — 추적만 해제, vault 데이터와 레포의 링크는 그대로 둔다.
- `purge` — vault 데이터를 즉시 삭제한다(확인 프롬프트 있음). 레포에 깨진
  링크가 남을 수 있다.

## 파일 격리 (vault)

| 명령 | 단축 | 설명 |
| --- | --- | --- |
| `pick <repo_key> <상대경로...>` | `p` | 지정한 파일을 vault로 옮기고 심볼릭 링크로 대체한다. |
| `pick <repo_key> --auto` | `p` | 설정된 `sensitive_patterns`로 후보를 자동 탐색해 격리한다. |
| `relink [repo_key]` | | 매니페스트 기준으로 현재 머신의 심볼릭 링크를 재생성한다. 생략 시 추적 중인 전체. |
| `audit [repo_key]` | | 깨진 링크·gitignore 미반영·드리프트를 점검한다. 생략 시 추적 중인 전체. |

**Windows에서 `pick`/`relink` 시 주의**: 심볼릭 링크 생성은 Windows에서
개발자 모드(설정 > 업데이트 및 보안 > 개발자용) 또는 관리자 권한이
필요하다. 없으면 `SymlinkPermissionError`가 발생하며, 이 경우 `pick`은
vault로 옮겼던 파일을 원래 자리로 롤백한다.

## 동기화 · 설정

| 명령 | 설명 |
| --- | --- |
| `sync --direction push\|pull` | `vault_root`와 `sync_target`(NAS 등) 사이를 미러링한다. |
| `set-vault-root <경로>` | `vault_root` 경로를 설정한다 (기본값: `~/.repo-sentinel/vault`). |
| `set-sync-target <경로>` | `sync_target` 경로를 설정한다. |
| `tui` | 번호 메뉴 기반의 16색 TUI 대시보드를 실행한다. |

## TUI 안에서

TUI는 자유 입력형 커맨드 대신 번호 메뉴로 동작한다. 숫자 키(또는 방향키+Enter)로
바로 아래 화면으로 이동하고, 어느 화면에서든 `Esc`로 이전 화면(메인 메뉴)으로
돌아갈 수 있다:

```
Repo Sentinel 메인 메뉴

1. 레포지토리 Track
2. 레포지토리 Untrack
3. 레포지토리 Relink
4. 레포지토리 관리
5. 파일 Pick
6. 환경설정

Q. 종료
```

- **1~3 (Track/Untrack/Relink)**: 각각 CLI의 `track`/`untrack`/`relink`와 같은
  동작을 폼으로 수행한다. `untrack`에서 `purge` 모드를 고르면 실행 전에 한 번
  더 확인 창이 뜬다.
- **4 (레포지토리 관리)**: 추적 목록을 표로 보여주고(경로·git 상태·이슈 개수),
  상단에 `Sync Push`/`Sync Pull` 버튼이 있다. 레포 하나를 선택하면 상세
  화면에서 `Audit 새로고침`/`Relink`/`Pick 파일 추가`/`Untrack`을 바로 실행할
  수 있다.
- **5 (파일 Pick)**: 레포를 고른 뒤 상대경로를 입력(자동완성 지원)하거나
  `자동 탐지(--auto)` 버튼으로 `sensitive_patterns` 후보를 한 번에 격리한다.
- **6 (환경설정)**: `vault_root`/`sync_target`/`sensitive_patterns`를 폼으로
  편집하고 저장한다.

자세한 아키텍처와 설계 배경은 [`docs/architecture.md`](architecture.md)를
참고하라.
