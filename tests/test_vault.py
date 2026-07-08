from pathlib import Path

from repo_sentinel.core.vault import ProtectedFile, load_manifest, repo_vault_dir, save_manifest


def test_manifest_round_trip(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path)
    manifest.repo("repo-a").files.append(
        ProtectedFile(relative_path="src/input/data.csv", gitignore_verified=True, protected_at="t")
    )
    save_manifest(tmp_path, manifest)

    reloaded = load_manifest(tmp_path)

    assert reloaded.repos["repo-a"].files[0].relative_path == "src/input/data.csv"
    assert reloaded.repos["repo-a"].files[0].gitignore_verified is True


def test_repo_vault_dir_naming(tmp_path: Path) -> None:
    assert repo_vault_dir(tmp_path, "repo-a") == tmp_path / "repo-a.repo-sentinel-vault"
