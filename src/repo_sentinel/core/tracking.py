"""추적 중인 레포 목록을 관리한다.

`scan`은 읽기 전용 탐색일 뿐 아무것도 등록하지 않는다. 사용자가 명시적으로
`track`한 레포만 여기 기록되며, 이때부터 vault/pick/relink/audit의
대상이 된다. 로컬 경로는 머신마다 다를 수 있으므로, 파일은 로컬(
`~/.repo-sentinel/tracked.json`)에 두되 다른 머신과 매칭 가능한
`repo_key`(core.repo_key 참고)를 기본 식별자로 사용한다.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from repo_sentinel.core import protect
from repo_sentinel.core.config import TRACKED_FILE, ensure_config_dir
from repo_sentinel.core.repo_key import compute_repo_key
from repo_sentinel.core.vault import load_manifest, repo_vault_dir


@dataclass
class TrackedRepo:
    repo_key: str
    path: str
    remote_url: str | None = None
    is_portable: bool = True
    tracked_at: str = ""


def _migrate_legacy_file() -> None:
    """구 버전(`subscriptions.json`, 필드명 `subscribed_at`)에서 한 번만 이관한다."""
    if TRACKED_FILE.exists():
        return
    legacy_file = TRACKED_FILE.parent / "subscriptions.json"
    if not legacy_file.exists():
        return
    data = json.loads(legacy_file.read_text(encoding="utf-8"))
    migrated = {}
    for key, value in data.items():
        value = dict(value)
        value["tracked_at"] = value.pop("subscribed_at", "")
        migrated[key] = value
    TRACKED_FILE.write_text(
        json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    legacy_file.unlink()


def load_tracked() -> dict[str, TrackedRepo]:
    _migrate_legacy_file()
    if not TRACKED_FILE.exists():
        return {}
    data = json.loads(TRACKED_FILE.read_text(encoding="utf-8"))
    return {key: TrackedRepo(**value) for key, value in data.items()}


def save_tracked(tracked: dict[str, TrackedRepo]) -> None:
    ensure_config_dir()
    payload = {key: asdict(entry) for key, entry in tracked.items()}
    TRACKED_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_tracked(
    repo_key: str, path: str, remote_url: str | None, is_portable: bool
) -> TrackedRepo:
    tracked = load_tracked()
    entry = TrackedRepo(
        repo_key=repo_key,
        path=path,
        remote_url=remote_url,
        is_portable=is_portable,
        tracked_at=datetime.now(timezone.utc).isoformat(),
    )
    tracked[repo_key] = entry
    save_tracked(tracked)
    return entry


def remove_tracked(repo_key: str) -> TrackedRepo | None:
    tracked = load_tracked()
    removed = tracked.pop(repo_key, None)
    if removed is not None:
        save_tracked(tracked)
    return removed


@dataclass
class TrackResult:
    entry: TrackedRepo | None
    warning: str | None = None
    error: str | None = None


def track_repo(repo_path: Path, custom_key: str | None = None) -> TrackResult:
    """CLI의 `track`과 TUI의 Track 화면이 공유하는 등록 로직.

    repo_key 계산, 이식성 경고, 별칭 충돌 검사까지 한 번에 처리해 두 진입점이
    같은 정책을 쓰도록 한다.
    """
    if not (repo_path / ".git").exists():
        return TrackResult(None, error=f"{repo_path}는 git 저장소가 아닙니다.")

    result = compute_repo_key(repo_path)
    warning = None
    if custom_key is None and not result.is_portable:
        warning = (
            "이 저장소에는 remote(origin)가 없어 폴더 이름을 repo_key로 사용합니다. "
            "다른 머신에서는 이 키로 vault를 재연결할 수 없습니다."
        )

    repo_key = custom_key or result.key
    if custom_key:
        warning = (
            f"사용자 지정 repo_key를 사용합니다: {repo_key} "
            "(다른 머신에서도 동일한 --key로 track해야 relink가 가능합니다)"
        )

    existing = load_tracked().get(repo_key)
    if existing is not None and Path(existing.path) != repo_path:
        return TrackResult(
            None,
            error=f"repo_key '{repo_key}'는 이미 다른 경로({existing.path})에서 사용 중입니다. "
            "다른 --key를 지정하세요.",
        )

    entry = add_tracked(
        repo_key=repo_key,
        path=str(repo_path),
        remote_url=result.remote_url,
        is_portable=result.is_portable,
    )
    return TrackResult(entry, warning=warning)


@dataclass
class UntrackResult:
    ok: bool
    message: str


def untrack_repo(repo_key: str, mode: str, vault_root: Path) -> UntrackResult:
    """CLI의 `untrack`과 TUI의 Untrack 화면이 공유하는 해제 로직.

    `mode`에 따른 vault 처리(복원/보존/삭제) 분기를 한곳에 모은다. `purge`
    확인 프롬프트는 호출자(CLI/TUI)의 표현 계층 책임으로 남겨둔다.
    """
    tracked = load_tracked()
    entry = tracked.get(repo_key)
    if entry is None:
        return UntrackResult(False, f"{repo_key}는 추적 중이 아닙니다.")

    repo_path = Path(entry.path)

    if mode == "purge":
        vault_dir = repo_vault_dir(vault_root, repo_key)
        if vault_dir.exists():
            shutil.rmtree(vault_dir)
    elif mode == "restore":
        manifest = load_manifest(vault_root)
        manifest_entry = manifest.repos.get(repo_key)
        if manifest_entry:
            for protected in list(manifest_entry.files):
                protect.restore_file(
                    repo_path, protected.relative_path, vault_root, repo_key, delete_vault_copy=True
                )
    # mode == "keep": vault 데이터는 그대로 두고 추적만 해제한다.

    remove_tracked(repo_key)
    return UntrackResult(True, f"{repo_key} 추적 해제 완료 (mode={mode})")
