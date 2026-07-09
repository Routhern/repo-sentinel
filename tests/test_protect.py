from pathlib import Path

import pytest

from repo_sentinel.core import protect
from repo_sentinel.core.vault import Manifest, ProtectedFile, load_manifest, repo_vault_dir, save_manifest


def _make_repo_with_file(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "src" / "input").mkdir(parents=True)
    target_file = repo / "src" / "input" / "data.csv"
    target_file.write_text("산지,품종\n충주,홍옥\n", encoding="utf-8")
    return repo, target_file


def test_protect_file_moves_and_links(tmp_path: Path, symlinks_supported: bool) -> None:
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo, target_file = _make_repo_with_file(tmp_path)
    vault_root = tmp_path / "vault"

    vault_file = protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")

    assert vault_file.read_text(encoding="utf-8") == "산지,품종\n충주,홍옥\n"
    assert target_file.is_symlink()
    assert target_file.resolve() == vault_file.resolve()

    manifest = load_manifest(vault_root)
    assert manifest.repos["repo-a"].find("src/input/data.csv") is not None


def test_protect_rolls_back_on_symlink_failure(tmp_path: Path, monkeypatch) -> None:
    repo, target_file = _make_repo_with_file(tmp_path)
    vault_root = tmp_path / "vault"

    monkeypatch.setattr(
        protect,
        "create_symlink",
        lambda link_path, target_path: (_ for _ in ()).throw(
            protect.SymlinkPermissionError("permission denied")
        ),
    )

    with pytest.raises(protect.SymlinkPermissionError):
        protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")

    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "산지,품종\n충주,홍옥\n"
    vault_dir = repo_vault_dir(vault_root, "repo-a")
    assert not any(p.is_file() for p in vault_dir.rglob("*")) if vault_dir.exists() else True
    manifest = load_manifest(vault_root)
    assert manifest.repos.get("repo-a") is None or manifest.repos["repo-a"].find(
        "src/input/data.csv"
    ) is None


def test_protect_rejects_already_protected(tmp_path: Path, symlinks_supported: bool) -> None:
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo, _ = _make_repo_with_file(tmp_path)
    vault_root = tmp_path / "vault"
    protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")

    with pytest.raises(protect.AlreadyProtectedError):
        protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")


def test_restore_file_round_trip(tmp_path: Path, symlinks_supported: bool) -> None:
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo, target_file = _make_repo_with_file(tmp_path)
    vault_root = tmp_path / "vault"
    protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")

    protect.restore_file(repo, "src/input/data.csv", vault_root, "repo-a", delete_vault_copy=True)

    assert target_file.exists()
    assert not target_file.is_symlink()
    assert target_file.read_text(encoding="utf-8") == "산지,품종\n충주,홍옥\n"
    manifest = load_manifest(vault_root)
    assert manifest.repos.get("repo-a") is None or manifest.repos["repo-a"].find(
        "src/input/data.csv"
    ) is None


def test_reflect_gitignore_marks_verified_when_already_ignored(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    manifest = Manifest()
    manifest.repo("repo-a").files.append(ProtectedFile(relative_path="secret.env", protected_at="t"))
    save_manifest(vault_root, manifest)
    monkeypatch.setattr(protect, "is_ignored", lambda *a, **k: True)

    added = protect.reflect_gitignore(repo, "repo-a", "secret.env", vault_root, should_add=False)

    assert added is False
    entry = load_manifest(vault_root).repos["repo-a"].find("secret.env")
    assert entry.gitignore_verified is True


def test_reflect_gitignore_adds_entry_when_should_add(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    manifest = Manifest()
    manifest.repo("repo-a").files.append(ProtectedFile(relative_path="secret.env", protected_at="t"))
    save_manifest(vault_root, manifest)
    monkeypatch.setattr(protect, "is_ignored", lambda *a, **k: False)

    added = protect.reflect_gitignore(repo, "repo-a", "secret.env", vault_root, should_add=True)

    assert added is True
    assert "secret.env" in (repo / ".gitignore").read_text(encoding="utf-8")
    entry = load_manifest(vault_root).repos["repo-a"].find("secret.env")
    assert entry.gitignore_verified is True


def test_reflect_gitignore_skips_when_should_add_false_and_not_ignored(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    manifest = Manifest()
    manifest.repo("repo-a").files.append(ProtectedFile(relative_path="secret.env", protected_at="t"))
    save_manifest(vault_root, manifest)
    monkeypatch.setattr(protect, "is_ignored", lambda *a, **k: False)

    added = protect.reflect_gitignore(repo, "repo-a", "secret.env", vault_root, should_add=False)

    assert added is False
    assert not (repo / ".gitignore").exists()
    entry = load_manifest(vault_root).repos["repo-a"].find("secret.env")
    assert entry.gitignore_verified is False


def test_relink_recreates_broken_link(tmp_path: Path, symlinks_supported: bool) -> None:
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo, target_file = _make_repo_with_file(tmp_path)
    vault_root = tmp_path / "vault"
    protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")
    target_file.unlink()  # 링크가 지워진 상황을 시뮬레이션

    relinked = protect.relink_repo(repo, "repo-a", vault_root)

    assert relinked == ["src/input/data.csv"]
    assert target_file.is_symlink()


def test_restore_file_rejects_path_traversal(tmp_path: Path) -> None:
    """조작된 manifest의 relative_path가 repo_path 밖의 파일을 지우지 못해야 한다."""
    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("victim data", encoding="utf-8")

    with pytest.raises(protect.UnsafeRelativePathError):
        protect.restore_file(repo, "../outside.txt", vault_root, "repo-a", delete_vault_copy=True)

    assert outside_file.exists()
    assert outside_file.read_text(encoding="utf-8") == "victim data"


def test_relink_repo_skips_unsafe_relative_path(tmp_path: Path, symlinks_supported: bool) -> None:
    """NAS로 동기화된 manifest에 `..`가 섞인 relative_path가 있어도 repo 밖에 링크를 만들지 않는다."""
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo = tmp_path / "repo"
    repo.mkdir()
    vault_root = tmp_path / "vault"
    vault_dir = repo_vault_dir(vault_root, "repo-a")
    vault_dir.mkdir(parents=True)
    (vault_dir / "payload.txt").write_text("attacker payload", encoding="utf-8")

    manifest = Manifest()
    manifest.repo("repo-a").files.append(
        ProtectedFile(relative_path="../outside-link.txt", protected_at="")
    )
    save_manifest(vault_root, manifest)

    with pytest.raises(protect.DriftError):
        protect.relink_repo(repo, "repo-a", vault_root)

    assert not (tmp_path / "outside-link.txt").exists()


def test_relink_reports_drift_without_overwriting(tmp_path: Path, symlinks_supported: bool) -> None:
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    repo, target_file = _make_repo_with_file(tmp_path)
    vault_root = tmp_path / "vault"
    protect.protect_file(repo, "src/input/data.csv", vault_root, "repo-a")
    target_file.unlink()
    target_file.write_text("누군가 실수로 복원한 진짜 파일", encoding="utf-8")

    with pytest.raises(protect.DriftError):
        protect.relink_repo(repo, "repo-a", vault_root)

    assert target_file.read_text(encoding="utf-8") == "누군가 실수로 복원한 진짜 파일"
