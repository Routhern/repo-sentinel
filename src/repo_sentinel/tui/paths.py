"""TUI 명령창의 경로 자동완성 후보를 계산한다.

셸의 탭 완성과 같은 방식: prefix의 마지막 디렉터리까지는 그대로 두고,
그 안에서 다음 구성요소 이름이 prefix로 시작하는 항목을 찾는다.
Textual에 대한 의존이 없는 순수 함수라 단위 테스트가 쉽다.
"""

from __future__ import annotations

from pathlib import Path


def relative_path_candidates(repo_path: Path, prefix: str) -> list[str]:
    # Path(...).name은 "."을 빈 이름으로 접어버리므로(Path(".").name == ""),
    # pathlib이 아니라 문자열 자체를 마지막 "/" 기준으로 나눈다.
    parent_str, _, name_prefix = prefix.rpartition("/")

    search_dir = repo_path / parent_str if parent_str else repo_path
    if not search_dir.is_dir():
        return []

    candidates: list[str] = []
    for entry in sorted(search_dir.iterdir()):
        if not entry.name.startswith(name_prefix):
            continue
        if entry.name.startswith(".") and not name_prefix.startswith("."):
            continue
        relative = entry.relative_to(repo_path)
        suffix = "/" if entry.is_dir() else ""
        candidates.append(f"{relative.as_posix()}{suffix}")
    return candidates
