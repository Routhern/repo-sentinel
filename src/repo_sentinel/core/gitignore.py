"""보호 대상 경로가 레포의 .gitignore에 반영되어 있는지 확인/추가한다.

protect가 만드는 심볼릭 링크는 로컬 절대경로(vault_root)를 가리키므로,
.gitignore로 무시되지 않으면 그 링크 파일 자체가 레포에 커밋되어 다른
머신에서 깨진 링크로 남는다. 이 모듈은 확인만 하며, 실제로 .gitignore를
수정할지는 호출자(CLI)가 사용자 확인을 받은 뒤 `add_entry`를 호출해 결정한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_ignored(repo_path: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "check-ignore", "-q", relative_path],
        capture_output=True,
    )
    return result.returncode == 0


def add_entry(repo_path: Path, relative_path: str) -> None:
    """레포의 .gitignore 끝에 relative_path를 추가한다. 이미 있으면 아무것도 하지 않는다."""
    gitignore_path = repo_path / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    lines = existing.splitlines()
    if relative_path in lines:
        return
    needs_newline = existing and not existing.endswith("\n")
    with gitignore_path.open("a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write(f"{relative_path}\n")


REGION_BEGIN = "# >>> repo-sentinel: pick 후보 패턴 >>>"
REGION_END = "# <<< repo-sentinel: pick 후보 패턴 <<<"


def ensure_region(repo_path: Path, default_patterns: list[str]) -> bool:
    """레포의 .gitignore에 repo-sentinel 리전이 없으면 default_patterns로 새로 만든다.

    이 리전의 패턴은 `pick --auto`/`track`이 pick 후보를 찾는 데 쓰인다. 이미
    리전이 있으면 손대지 않고 그대로 둔다 — 패턴 추가/삭제는 사용자가 이
    구간을 직접 편집하는 수동 과정이며, repo-sentinel이 track할 때마다
    전역 설정으로 덮어쓰지 않는다. 새로 만들었으면 True를 반환한다.
    """
    gitignore_path = repo_path / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    if REGION_BEGIN in existing:
        return False

    region_lines = [
        REGION_BEGIN,
        "# 이 구간의 패턴에 매칭되는 파일은 pick 후보로 제안됩니다.",
        "# 패턴을 추가/삭제하려면 이 구간을 직접 편집하세요 (자동으로 갱신되지 않습니다).",
        *default_patterns,
        REGION_END,
    ]
    needs_newline = existing and not existing.endswith("\n")
    with gitignore_path.open("a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write("\n".join(region_lines) + "\n")
    return True


def read_region_patterns(repo_path: Path) -> list[str] | None:
    """.gitignore의 repo-sentinel 리전에서 패턴 목록을 읽는다. 리전이 없으면 None."""
    gitignore_path = repo_path / ".gitignore"
    if not gitignore_path.exists():
        return None
    lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(REGION_BEGIN)
        end = lines.index(REGION_END, start)
    except ValueError:
        return None
    return [
        line.strip()
        for line in lines[start + 1 : end]
        if line.strip() and not line.strip().startswith("#")
    ]


def resolve_patterns(repo_path: Path, fallback_patterns: list[str]) -> list[str]:
    """리전이 있으면 리전 패턴을, 없으면 fallback_patterns(전역 설정)를 쓴다."""
    region_patterns = read_region_patterns(repo_path)
    return region_patterns if region_patterns is not None else fallback_patterns
