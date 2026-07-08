from pathlib import Path

import pytest

from repo_sentinel.core import protect
from repo_sentinel.core.vault import load_manifest, repo_vault_dir


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
