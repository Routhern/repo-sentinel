"""vault_root와 sync_target(예: 시놀로지 드라이브 로컬 폴더) 사이를 미러링한다.

레포를 전혀 알지 못한 채 두 로컬 디렉터리 트리만 다룬다는 것이 핵심이다.
다기기 동기화·버전 관리·충돌 해결은 NAS/동기화 클라이언트의 책임이며,
repo-sentinel은 그 클라이언트가 감시하는 로컬 폴더(sync_target)와 vault_root
사이를 mtime 기준 "최신 파일 우선"으로 맞추는 거울 역할만 한다.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _mirror(source_root: Path, dest_root: Path) -> list[str]:
    """source_root의 각 파일을 dest_root로 복사한다. dest에 더 최신 파일이 있으면 건너뛴다."""
    if not source_root.exists():
        return []

    copied: list[str] = []
    for source_file in source_root.rglob("*"):
        if source_file.is_dir():
            continue
        relative = source_file.relative_to(source_root)
        dest_file = dest_root / relative

        if dest_file.exists() and dest_file.stat().st_mtime >= source_file.stat().st_mtime:
            continue

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source_file), str(dest_file))
        copied.append(relative.as_posix())

    return copied


def push_to_sync_target(vault_root: Path, sync_target: Path) -> list[str]:
    """vault_root -> sync_target으로 최신 파일을 복사한다."""
    return _mirror(vault_root, sync_target)


def pull_from_sync_target(vault_root: Path, sync_target: Path) -> list[str]:
    """sync_target -> vault_root로 최신 파일을 복사한다."""
    return _mirror(sync_target, vault_root)
