from pathlib import Path

import pytest

from repo_sentinel.core import audit
from repo_sentinel.core.vault import ProtectedFile, load_manifest, repo_vault_dir, save_manifest


def _seed_manifest(vault_root: Path, repo_key: str, relative_path: str, *, gitignore_verified: bool) -> None:
    manifest = load_manifest(vault_root)
    manifest.repo(repo_key).files.append(
        ProtectedFile(relative_path=relative_path, gitignore_verified=gitignore_verified, protected_at="t")
    )
    save_manifest(vault_root, manifest)


def test_audit_no_subscription_entry_returns_empty(tmp_path: Path) -> None:
    assert audit.audit_repo(tmp_path / "repo", "unknown-repo", tmp_path / "vault") == []


def test_audit_detects_missing_link_and_vault_file(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    _seed_manifest(vault_root, "repo-a", "src/input/data.csv", gitignore_verified=True)
    monkeypatch.setattr(audit, "is_ignored", lambda *a, **k: True)

    issues = audit.audit_repo(repo, "repo-a", vault_root)

    kinds = {i.kind for i in issues}
    assert "broken_link" in kinds
    assert "vault_file_missing" in kinds


def test_audit_detects_drift_and_gitignore_missing(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "input").mkdir(parents=True)
    (repo / "src" / "input" / "data.csv").write_text("실수로 복원된 실제 파일", encoding="utf-8")

    vault_root = tmp_path / "vault"
    vault_file = repo_vault_dir(vault_root, "repo-a") / "src" / "input" / "data.csv"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("vault 원본", encoding="utf-8")
    _seed_manifest(vault_root, "repo-a", "src/input/data.csv", gitignore_verified=False)
    monkeypatch.setattr(audit, "is_ignored", lambda *a, **k: False)

    issues = audit.audit_repo(repo, "repo-a", vault_root)

    kinds = {i.kind for i in issues}
    assert kinds == {"drift", "gitignore_missing"}


def test_audit_clean_state_reports_nothing(tmp_path: Path, symlinks_supported: bool) -> None:
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo = tmp_path / "repo"
    (repo / "src" / "input").mkdir(parents=True)
    vault_root = tmp_path / "vault"
    vault_file = repo_vault_dir(vault_root, "repo-a") / "src" / "input" / "data.csv"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("vault 원본", encoding="utf-8")
    (repo / "src" / "input" / "data.csv").symlink_to(vault_file)
    _seed_manifest(vault_root, "repo-a", "src/input/data.csv", gitignore_verified=True)

    assert audit.audit_repo(repo, "repo-a", vault_root) == []
