"""vault_root 안의 매니페스트(누가 무엇을 보호하고 있는지)를 관리한다.

매니페스트는 vault_root 자체에 저장한다(설정 디렉터리가 아니라). vault_root는
NAS를 통해 다른 머신과 동기화되는 대상이므로, 새 머신에서 vault 내용을 받은
뒤 `relink`만으로 그 머신의 로컬 상태를 재구성하려면 "무엇을 어디에 연결해야
하는지"에 대한 정보도 함께 동기화되어야 하기 때문이다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

MANIFEST_FILENAME = "manifest.json"


def vault_dir_name(repo_key: str) -> str:
    return f"{repo_key}.repo-sentinel-vault"


def repo_vault_dir(vault_root: Path, repo_key: str) -> Path:
    return vault_root / vault_dir_name(repo_key)


@dataclass
class ProtectedFile:
    relative_path: str  # 레포 루트 기준 상대 경로 (protect 당시 기준)
    gitignore_verified: bool = False
    protected_at: str = ""


@dataclass
class RepoVaultEntry:
    files: list[ProtectedFile] = field(default_factory=list)

    def find(self, relative_path: str) -> ProtectedFile | None:
        for f in self.files:
            if f.relative_path == relative_path:
                return f
        return None


@dataclass
class Manifest:
    repos: dict[str, RepoVaultEntry] = field(default_factory=dict)

    def repo(self, repo_key: str) -> RepoVaultEntry:
        return self.repos.setdefault(repo_key, RepoVaultEntry())


def _manifest_path(vault_root: Path) -> Path:
    return vault_root / MANIFEST_FILENAME


def load_manifest(vault_root: Path) -> Manifest:
    path = _manifest_path(vault_root)
    if not path.exists():
        return Manifest()
    data = json.loads(path.read_text(encoding="utf-8"))
    repos = {
        repo_key: RepoVaultEntry(
            files=[ProtectedFile(**f) for f in entry.get("files", [])]
        )
        for repo_key, entry in data.get("repos", {}).items()
    }
    return Manifest(repos=repos)


def save_manifest(vault_root: Path, manifest: Manifest) -> None:
    vault_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "repos": {
            repo_key: {"files": [asdict(f) for f in entry.files]}
            for repo_key, entry in manifest.repos.items()
        }
    }
    _manifest_path(vault_root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
