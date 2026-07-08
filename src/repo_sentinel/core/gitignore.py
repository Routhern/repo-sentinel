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
