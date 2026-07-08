# repo-sentinel

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PC 전역에 흩어진 git 저장소를 중앙 목록화하고, 변경 사항을 감지하며,
dotenv·개인 파일 같은 민감한 산출물을 저장소 밖(NAS 등)에서 안전하게
동기화하기 위한 CLI 도구입니다. 기획 배경은 [CONTEXTS_AND_PLAN.md](./CONTEXTS_AND_PLAN.md)를 참고하세요.

## 시작하기

```bash
uv sync
uv run repo-sentinel --help

uv run repo-sentinel scan .                  # 저장소 탐색 (읽기 전용)
uv run repo-sentinel track <경로>             # 추적 대상으로 등록 (단축: t)
uv run repo-sentinel track <경로> --key <별칭>  # repo_key로 짧은 별칭 직접 지정 (-k)
uv run repo-sentinel pick <repo_key> <상대경로>  # 민감 파일을 vault로 격리 (단축: p)
uv run repo-sentinel sync --direction push   # vault_root -> sync_target(NAS) 동기화

uv run repo-sentinel tui                     # 번호 메뉴 기반 16색 TUI 대시보드
```

Windows에서 심볼릭 링크 생성 권한(개발자 모드)을 켤 수 없다면
`bin/repo-sentinel-admin.vbs`를 더블클릭해 관리자 권한으로 실행하세요.

전체 명령어 참고는 [`docs/commands.md`](docs/commands.md), 내부 설계는
[`docs/architecture.md`](docs/architecture.md)에 있습니다.

## 원칙

- 이 저장소 자체는 순수 소스코드만 포함하며, 데이터나 시크릿을 커밋하지 않습니다.
- 사용자별 데이터(추적 목록, 설정)는 항상 `~/.repo-sentinel/` 아래에 저장됩니다.
- NAS는 여러 기기 간 파일을 동기화·백업하는 단순 저장소일 뿐이며, 무엇을 보호하고
  어떻게 연결할지는 항상 로컬 `vault_root`를 기준으로 repo-sentinel이 결정합니다.

## 더 읽어보기

- [`docs/`](docs/) — 명령어 참고와 아키텍처 문서 모음.
- [`CHANGELOG.md`](CHANGELOG.md) — 버전별 변경 이력.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — 개발 환경 설정과 기여 방법.
- [`LICENSE`](LICENSE) — MIT 라이선스.
