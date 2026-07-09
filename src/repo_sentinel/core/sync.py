"""vault_root와 sync_target(예: 시놀로지 드라이브 로컬 폴더) 사이를 미러링한다.

레포를 전혀 알지 못한 채 두 로컬 디렉터리 트리만 다룬다는 것이 핵심이다.
다기기 동기화·버전 관리·충돌 해결은 NAS/동기화 클라이언트의 책임이며,
repo-sentinel은 그 클라이언트가 감시하는 로컬 폴더(sync_target)와 vault_root
사이를 mtime 기준 "최신 파일 우선"으로 맞추는 거울 역할만 한다.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _mirror(source_root: Path, dest_root: Path) -> list[str]:
    """source_root의 각 파일을 dest_root로 복사한다. dest에 더 최신 파일이 있으면 건너뛴다.

    `sync_target`(NAS 등 외부에서 쓰기 가능한 폴더)이 source가 될 수 있으므로,
    그 안에 심볼릭 링크가 심겨 있어도 링크가 가리키는 파일 내용까지 vault로
    끌려 들어오지 않도록 심볼릭 링크(파일/디렉터리 모두)는 건너뛴다.
    `os.walk`의 기본값(`followlinks=False`)이 심볼릭 디렉터리 안으로는 애초에
    내려가지 않게 막아 주고, 파일 심볼릭 링크는 아래에서 명시적으로 걸러낸다.
    """
    if not source_root.exists():
        return []

    copied: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(source_root, followlinks=False):
        current_dir = Path(dirpath)
        for filename in filenames:
            source_file = current_dir / filename
            if source_file.is_symlink():
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
