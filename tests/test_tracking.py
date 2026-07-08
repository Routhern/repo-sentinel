from pathlib import Path

from repo_sentinel.core import tracking
from repo_sentinel.core.vault import Manifest, ProtectedFile, repo_vault_dir, save_manifest


def test_add_and_load_tracked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")

    tracking.add_tracked(
        repo_key="github.com__me__proj", path="/repos/proj", remote_url="git@github.com:me/proj.git", is_portable=True
    )

    loaded = tracking.load_tracked()
    assert loaded["github.com__me__proj"].path == "/repos/proj"


def test_remove_tracked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    tracking.add_tracked(repo_key="k", path="/p", remote_url=None, is_portable=False)

    removed = tracking.remove_tracked("k")

    assert removed is not None
    assert tracking.load_tracked() == {}


def test_migrates_legacy_subscriptions_file(tmp_path: Path, monkeypatch) -> None:
    tracked_file = tmp_path / "tracked.json"
    monkeypatch.setattr(tracking, "TRACKED_FILE", tracked_file)

    legacy_file = tmp_path / "subscriptions.json"
    legacy_file.write_text(
        '{"repo-a": {"repo_key": "repo-a", "path": "/repos/a", '
        '"remote_url": null, "is_portable": false, "subscribed_at": "2020-01-01T00:00:00+00:00"}}',
        encoding="utf-8",
    )

    loaded = tracking.load_tracked()

    assert loaded["repo-a"].path == "/repos/a"
    assert loaded["repo-a"].tracked_at == "2020-01-01T00:00:00+00:00"
    assert tracked_file.exists()
    assert not legacy_file.exists()


def test_track_repo_rejects_non_git_directory(tmp_path: Path) -> None:
    result = tracking.track_repo(tmp_path / "not-a-repo")

    assert result.entry is None
    assert result.error is not None


def test_track_repo_computes_default_key_and_warns_without_remote(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    result = tracking.track_repo(repo)

    assert result.error is None
    assert result.entry is not None
    assert result.entry.path == str(repo)
    assert result.warning is not None


def test_track_repo_with_custom_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    result = tracking.track_repo(repo, "myrepo")

    assert result.error is None
    assert result.entry.repo_key == "myrepo"
    assert result.warning is not None


def test_track_repo_rejects_key_collision_with_different_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    (repo_a / ".git").mkdir(parents=True)
    (repo_b / ".git").mkdir(parents=True)

    tracking.track_repo(repo_a, "dup")
    result = tracking.track_repo(repo_b, "dup")

    assert result.entry is None
    assert result.error is not None


def test_untrack_repo_unknown_repo_returns_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")

    result = tracking.untrack_repo("nope", "keep", tmp_path / "vault")

    assert result.ok is False


def test_untrack_repo_restore_mode_moves_vault_file_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    vault_file = repo_vault_dir(vault_root, "repo-a") / "secret.env"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("secret")
    manifest = Manifest()
    manifest.repo("repo-a").files.append(
        ProtectedFile(relative_path="secret.env", gitignore_verified=True, protected_at="t")
    )
    save_manifest(vault_root, manifest)
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    result = tracking.untrack_repo("repo-a", "restore", vault_root)

    assert result.ok is True
    assert (repo / "secret.env").read_text() == "secret"
    assert not vault_file.exists()
    assert tracking.load_tracked() == {}


def test_untrack_repo_keep_mode_preserves_vault(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    result = tracking.untrack_repo("repo-a", "keep", vault_root)

    assert result.ok is True
    assert tracking.load_tracked() == {}


def test_untrack_repo_purge_mode_removes_vault_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    vault_dir = repo_vault_dir(vault_root, "repo-a")
    vault_dir.mkdir(parents=True)
    (vault_dir / "secret.env").write_text("secret")
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    result = tracking.untrack_repo("repo-a", "purge", vault_root)

    assert result.ok is True
    assert not vault_dir.exists()
    assert tracking.load_tracked() == {}
