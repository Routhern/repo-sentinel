"""레포를 머신에 독립적으로 식별하는 repo_key를 계산한다.

로컬 클론 경로는 머신마다 다를 수 있으므로 (예: Windows에서는
`C:\\Users\\me\\repo`, macOS에서는 `/Users/me/dev/repo`), vault manifest의
키로 로컬 경로를 쓰면 다른 머신에서 relink가 불가능하다. 대신 git remote
"origin" URL을 정규화해 안정적인 키를 만든다. remote가 없는 로컬 전용
저장소는 폴더 이름으로 대체하되, 이 경우 다른 머신 간 이식성이 보장되지
않는다는 점을 호출자에게 알려야 한다.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SCHEME_RE = re.compile(r"^\w+://")
_SSH_SHORTHAND_RE = re.compile(r"^git@([^:]+):(.+)$")


@dataclass
class RepoKeyResult:
    key: str
    remote_url: str | None
    is_portable: bool  # False면 remote가 없어 폴더명으로 대체했다는 뜻


def get_remote_url(repo_path: Path, remote: str = "origin") -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", remote],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def normalize_remote_url(url: str) -> str:
    """https://github.com/owner/repo.git, git@github.com:owner/repo.git 등을
    github.com__owner__repo 형태로 정규화한다."""
    ssh_match = _SSH_SHORTHAND_RE.match(url)
    if ssh_match:
        host, path = ssh_match.group(1), ssh_match.group(2)
    else:
        without_scheme = _SCHEME_RE.sub("", url)
        without_scheme = without_scheme.split("@")[-1]  # user@host/path 형태 제거
        host, _, path = without_scheme.partition("/")

    path = path.removesuffix(".git").strip("/")
    parts = [host, *path.split("/")]
    parts = [p for p in parts if p]
    return "__".join(parts)


def compute_repo_key(repo_path: Path) -> RepoKeyResult:
    remote_url = get_remote_url(repo_path)
    if remote_url:
        return RepoKeyResult(
            key=normalize_remote_url(remote_url), remote_url=remote_url, is_portable=True
        )
    return RepoKeyResult(key=repo_path.name, remote_url=None, is_portable=False)
