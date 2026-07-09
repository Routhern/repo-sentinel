"""레포의 민감 파일을 vault로 격리(protect)하고, 필요 시 복원(restore)하거나
현재 머신 기준으로 심볼릭 링크를 재생성(relink)한다.

기준 상태는 항상 vault_root다. 레포 쪽에 남는 것은 vault_root를 가리키는
심볼릭 링크뿐이며, 이 링크는 머신마다 다시 만들어져야 한다(다른 머신의
vault_root 경로가 다를 수 있으므로 NAS로 동기화되는 대상이 아니다).
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from repo_sentinel.core.vault import ProtectedFile, load_manifest, repo_vault_dir, save_manifest


class SymlinkPermissionError(RuntimeError):
    pass


class AlreadyProtectedError(RuntimeError):
    pass


class DriftError(RuntimeError):
    """심볼릭 링크가 있어야 할 자리에 실제 파일이 존재하는 경우."""


class UnsafeRelativePathError(RuntimeError):
    """manifest에 기록된 relative_path가 허용된 디렉터리를 벗어나려는 경우."""


def _resolve_within(base: Path, relative_path: str) -> Path:
    """base/relative_path를 base 밖으로 벗어나지 않는지 검증한 뒤 반환한다.

    manifest.json은 vault_root와 함께 sync_target(NAS)을 통해 다른 머신과
    동기화되므로, `..`나 절대 경로가 섞인 relative_path가 들어와도 repo_path나
    vault_root 밖의 임의 파일을 건드리지 않도록 여기서 막는다. 마지막 구성요소
    자체는 resolve하지 않는데, 그 자리가 심볼릭 링크인지 판별하는 것이 호출부의
    책임이라 여기서 링크를 따라가버리면 그 판별이 무의미해지기 때문이다.
    """
    base_resolved = base.resolve()
    joined = base_resolved / relative_path
    candidate = joined.parent.resolve() / joined.name
    if not candidate.is_relative_to(base_resolved):
        raise UnsafeRelativePathError(f"{relative_path!r}는 {base}를 벗어나는 경로입니다")
    return candidate


def create_symlink(link_path: Path, target_path: Path) -> None:
    try:
        link_path.symlink_to(target_path)
    except OSError as e:
        raise SymlinkPermissionError(
            "심볼릭 링크 생성에 실패했습니다. Windows에서는 개발자 모드를 켜거나 "
            "관리자 권한으로 실행해야 합니다 (설정 > 업데이트 및 보안 > 개발자용 > "
            "개발자 모드). macOS/Linux에서는 대상 디렉터리에 쓰기 권한이 있는지 "
            f"확인하세요. 원인: {e}"
        ) from e


def find_candidates(repo_path: Path, patterns: list[str]) -> list[str]:
    """sensitive_patterns에 매칭되는, 아직 심볼릭 링크가 아닌 파일들의 상대경로를 찾는다."""
    matches: set[Path] = set()
    for pattern in patterns:
        matches.update(p for p in repo_path.rglob(pattern) if p.is_file() and not p.is_symlink())
    return sorted(str(p.relative_to(repo_path)) for p in matches)


def protect_file(repo_path: Path, relative_path: str, vault_root: Path, repo_key: str) -> Path:
    """repo_path/relative_path를 vault로 옮기고 그 자리에 심볼릭 링크를 만든다."""
    source = repo_path / relative_path
    if source.is_symlink():
        raise AlreadyProtectedError(f"{relative_path}는 이미 보호되어 있습니다 (심볼릭 링크)")
    if not source.exists():
        raise FileNotFoundError(f"{source}가 존재하지 않습니다")

    vault_file = repo_vault_dir(vault_root, repo_key) / relative_path
    vault_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(vault_file))
    try:
        create_symlink(source, vault_file)
    except SymlinkPermissionError:
        shutil.move(str(vault_file), str(source))  # 실패 시 원래 자리로 롤백
        raise

    manifest = load_manifest(vault_root)
    entry = manifest.repo(repo_key)
    existing = entry.find(relative_path)
    protected_at = datetime.now(timezone.utc).isoformat()
    if existing:
        entry.files.remove(existing)
    entry.files.append(
        ProtectedFile(relative_path=relative_path, gitignore_verified=False, protected_at=protected_at)
    )
    save_manifest(vault_root, manifest)
    return vault_file


def mark_gitignore_verified(vault_root: Path, repo_key: str, relative_path: str) -> None:
    manifest = load_manifest(vault_root)
    entry = manifest.repo(repo_key)
    existing = entry.find(relative_path)
    if existing is None:
        return
    entry.files.remove(existing)
    entry.files.append(replace(existing, gitignore_verified=True))
    save_manifest(vault_root, manifest)


def restore_file(
    repo_path: Path, relative_path: str, vault_root: Path, repo_key: str, *, delete_vault_copy: bool
) -> None:
    """vault의 실제 파일을 레포 쪽으로 되돌리고 심볼릭 링크를 제거한다."""
    link_path = _resolve_within(repo_path, relative_path)
    vault_file = _resolve_within(repo_vault_dir(vault_root, repo_key), relative_path)

    if not vault_file.exists():
        raise FileNotFoundError(f"vault에 {vault_file}가 없습니다")

    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()

    link_path.parent.mkdir(parents=True, exist_ok=True)
    if delete_vault_copy:
        shutil.move(str(vault_file), str(link_path))
    else:
        shutil.copy2(str(vault_file), str(link_path))

    if delete_vault_copy:
        manifest = load_manifest(vault_root)
        entry = manifest.repo(repo_key)
        existing = entry.find(relative_path)
        if existing:
            entry.files.remove(existing)
            save_manifest(vault_root, manifest)


def relink_repo(repo_path: Path, repo_key: str, vault_root: Path) -> list[str]:
    """매니페스트 기준으로 현재 머신의 심볼릭 링크를 재생성한다.

    반환값은 실제로 (재)생성한 relative_path 목록이다. 링크 자리에 실제
    파일이 있는 드리프트 상태는 건드리지 않고 DriftError로 알린다.
    """
    manifest = load_manifest(vault_root)
    entry = manifest.repos.get(repo_key)
    if entry is None:
        return []

    relinked: list[str] = []
    drifted: list[str] = []
    unsafe: list[str] = []
    for protected in entry.files:
        try:
            link_path = _resolve_within(repo_path, protected.relative_path)
            vault_file = _resolve_within(repo_vault_dir(vault_root, repo_key), protected.relative_path)
        except UnsafeRelativePathError:
            unsafe.append(protected.relative_path)
            continue

        if link_path.is_symlink():
            if link_path.exists():
                continue  # 이미 정상 링크
            link_path.unlink()  # 깨진 링크 제거 후 재생성
        elif link_path.exists():
            drifted.append(protected.relative_path)
            continue

        link_path.parent.mkdir(parents=True, exist_ok=True)
        create_symlink(link_path, vault_file)
        relinked.append(protected.relative_path)

    if drifted or unsafe:
        messages = []
        if drifted:
            messages.append(
                "다음 경로는 심볼릭 링크가 아닌 실제 파일이 있어 건드리지 않았습니다: "
                + ", ".join(drifted)
            )
        if unsafe:
            messages.append(
                "다음 경로는 repo/vault 밖을 가리켜 건너뛰었습니다: " + ", ".join(unsafe)
            )
        raise DriftError("; ".join(messages))
    return relinked
