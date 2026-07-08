# 기여 가이드

## 개발 환경 설정

의존성 관리는 [uv](https://docs.astral.sh/uv/)를 사용한다.

```bash
uv sync                          # 의존성 설치 (.venv 생성)
uv run repo-sentinel --help      # CLI 실행
```

전체 CLI 명령어는 [`docs/commands.md`](docs/commands.md), 아키텍처는
[`docs/architecture.md`](docs/architecture.md)를 참고하라.

## 테스트

```bash
uv run pytest                                    # 전체 테스트 실행
uv run pytest tests/test_protect.py -q           # 단일 파일
uv run pytest tests/test_tui_app.py -q           # TUI 헤드리스 스모크 테스트
```

**Windows에서 심볼릭 링크 관련 테스트**: `pick`/`relink`가 만드는 심볼릭
링크는 Windows에서 개발자 모드(설정 > 업데이트 및 보안 > 개발자용) 또는
관리자 권한이 필요하다. 권한이 없으면 `tests/conftest.py`의
`symlinks_supported` 픽스처가 이를 감지해 관련 테스트를 자동으로 skip한다.

## 핵심 원칙

- 이 저장소 자체는 순수 소스코드만 포함해야 한다. 사용자별 데이터(추적
  목록, vault 설정 등)는 절대 저장소 트리 안에 쓰지 말고 항상
  `~/.repo-sentinel/`(`core/config.py`의 `CONFIG_DIR`)에 저장한다.
- CLI(`cli.py`)와 TUI(`tui/app.py`)는 항상 `core/`의 같은 함수를 호출한다.
  둘 중 한쪽에만 정책 로직을 새로 만들지 않는다.
- vault_root가 기준 상태이며 NAS(`sync_target`)는 이를 미러링하는 단순
  저장소로만 다룬다. 자세한 배경은
  [`docs/architecture.md`](docs/architecture.md)를 보라.

## 커밋 및 PR

- 커밋 메시지는 변경의 "왜"를 한두 문장으로 설명한다.
- 사용자 관찰 가능한 변경(신규 명령어, 동작 변경, 버그 수정 등)은
  [`CHANGELOG.md`](CHANGELOG.md)의 `Unreleased` 항목에 함께 기록한다.
- PR을 올리기 전에 `uv run pytest`가 통과하는지 확인한다.

## 라이선스

기여한 코드는 이 저장소의 [MIT 라이선스](LICENSE)로 배포된다.
