# repo-sentinel

PC 전역에 흩어진 git 저장소를 중앙 목록화하고, 변경 사항을 감지하며,
dotenv·개인 파일 같은 민감한 산출물을 저장소 밖(NAS 등)에서 안전하게
동기화하기 위한 CLI 도구입니다. 기획 배경은 [CONTEXTS_AND_PLAN.md](./CONTEXTS_AND_PLAN.md)를 참고하세요.

## 시작하기

```bash
uv sync
uv run repo-sentinel --help

uv run repo-sentinel scan .                  # 저장소 탐색 (읽기 전용)
uv run repo-sentinel subscribe <경로>         # 추적 대상으로 등록
uv run repo-sentinel protect <repo_key> <상대경로>  # 민감 파일을 vault로 격리
uv run repo-sentinel sync --direction push   # vault_root -> sync_target(NAS) 동기화

uv run repo-sentinel tui                     # 자동완성이 되는 16색 TUI 대시보드
```

## 원칙

- 이 저장소 자체는 순수 소스코드만 포함하며, 데이터나 시크릿을 커밋하지 않습니다.
- 사용자별 데이터(구독 목록, 설정)는 항상 `~/.repo-sentinel/` 아래에 저장됩니다.
- NAS는 여러 기기 간 파일을 동기화·백업하는 단순 저장소일 뿐이며, 무엇을 보호하고
  어떻게 연결할지는 항상 로컬 `vault_root`를 기준으로 repo-sentinel이 결정합니다.
