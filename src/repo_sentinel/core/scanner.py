"""파일시스템에서 git 저장소를 탐색한다."""

from __future__ import annotations

from pathlib import Path

# 탐색 시 내려가지 않을 디렉터리 (성능 및 무의미한 재귀 방지)
SKIP_DIR_NAMES = {"node_modules", ".venv", "venv", "__pycache__", ".git"}


def find_git_repos(root: Path) -> list[Path]:
    """root 이하에서 .git 디렉터리를 가진 저장소의 루트 경로 목록을 반환한다."""
    repos: list[Path] = []
    _walk(root, repos)
    return repos


def _walk(current: Path, repos: list[Path]) -> None:
    try:
        entries = list(current.iterdir())
    except (PermissionError, OSError):
        return

    if (current / ".git").exists():
        repos.append(current)
        return  # 저장소 내부는 더 탐색하지 않는다 (서브모듈 제외)

    for entry in entries:
        if entry.is_dir() and entry.name not in SKIP_DIR_NAMES:
            _walk(entry, repos)
