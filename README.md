# repo-sentinel

PC 전역에 흩어진 git 저장소를 중앙 목록화하고, 변경 사항을 감지하며,
dotenv·개인 파일 같은 민감한 산출물을 저장소 밖(NAS 등)에서 안전하게
동기화하기 위한 CLI 도구입니다. 기획 배경은 [CONTEXTS_AND_PLAN.md](./CONTEXTS_AND_PLAN.md)를 참고하세요.

## 시작하기

```bash
uv sync
uv run repo-sentinel --help
```

## 원칙

- 이 저장소 자체는 순수 소스코드만 포함하며, 데이터나 시크릿을 커밋하지 않습니다.
- 사용자별 데이터(레지스트리, 설정)는 항상 `~/.repo-sentinel/` 아래에 저장됩니다.
