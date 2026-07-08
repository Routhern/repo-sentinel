"""보호 중인 파일들의 상태를 점검한다: 깨진 링크, .gitignore 미반영, 드리프트."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_sentinel.core.gitignore import is_ignored
from repo_sentinel.core.vault import load_manifest, repo_vault_dir


@dataclass
class AuditIssue:
    repo_key: str
    relative_path: str
    kind: str  # "broken_link" | "gitignore_missing" | "drift" | "vault_file_missing"
    detail: str


def audit_repo(repo_path: Path, repo_key: str, vault_root: Path) -> list[AuditIssue]:
    manifest = load_manifest(vault_root)
    entry = manifest.repos.get(repo_key)
    if entry is None:
        return []

    issues: list[AuditIssue] = []
    for protected in entry.files:
        link_path = repo_path / protected.relative_path
        vault_file = repo_vault_dir(vault_root, repo_key) / protected.relative_path

        if link_path.is_symlink():
            if not link_path.exists():
                issues.append(
                    AuditIssue(
                        repo_key, protected.relative_path, "broken_link",
                        "링크가 가리키는 vault 파일이 없습니다. `relink` 또는 vault 동기화를 확인하세요.",
                    )
                )
        elif link_path.exists():
            issues.append(
                AuditIssue(
                    repo_key, protected.relative_path, "drift",
                    "심볼릭 링크가 아닌 실제 파일이 존재합니다. 다시 protect가 필요할 수 있습니다.",
                )
            )
        else:
            issues.append(
                AuditIssue(
                    repo_key, protected.relative_path, "broken_link",
                    "레포에 파일도 링크도 없습니다.",
                )
            )

        if not vault_file.exists():
            issues.append(
                AuditIssue(
                    repo_key, protected.relative_path, "vault_file_missing",
                    "매니페스트에는 있지만 vault에 실제 파일이 없습니다.",
                )
            )

        if not protected.gitignore_verified and not is_ignored(repo_path, protected.relative_path):
            issues.append(
                AuditIssue(
                    repo_key, protected.relative_path, "gitignore_missing",
                    "이 경로가 레포의 .gitignore에 반영되어 있지 않습니다. "
                    "심볼릭 링크가 그대로 커밋될 위험이 있습니다.",
                )
            )

    return issues
