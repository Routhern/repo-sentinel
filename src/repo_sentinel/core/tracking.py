"""추적 중인 레포 목록을 관리한다.

`scan`은 읽기 전용 탐색일 뿐 아무것도 등록하지 않는다. 사용자가 명시적으로
`track`한 레포만 여기 기록되며, 이때부터 vault/pick/relink/audit의
대상이 된다. 로컬 경로는 머신마다 다를 수 있으므로, 파일은 로컬(
`~/.repo-sentinel/tracked.json`)에 두되 다른 머신과 매칭 가능한
`repo_key`(core.repo_key 참고)를 기본 식별자로 사용한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from repo_sentinel.core.config import TRACKED_FILE, ensure_config_dir


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
