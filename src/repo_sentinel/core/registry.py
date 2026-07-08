"""탐지된 git 저장소들의 중앙 목록을 관리한다."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from repo_sentinel.core.config import REGISTRY_FILE, ensure_config_dir


@dataclass
class RepoEntry:
    path: str
    remote_url: str | None = None


def load_registry() -> list[RepoEntry]:
    if not REGISTRY_FILE.exists():
        return []
    data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return [RepoEntry(**entry) for entry in data]


def save_registry(entries: list[RepoEntry]) -> None:
    ensure_config_dir()
    REGISTRY_FILE.write_text(
        json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def merge_scanned_paths(paths: list[str]) -> list[RepoEntry]:
    """스캔 결과를 기존 레지스트리와 병합해 반환한다 (기존 메타데이터 보존)."""
    existing = {e.path: e for e in load_registry()}
    merged = [existing.get(p, RepoEntry(path=p)) for p in paths]
    return merged
