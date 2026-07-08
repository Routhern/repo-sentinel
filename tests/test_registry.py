from pathlib import Path

from repo_sentinel.core import registry


def test_merge_scanned_paths_preserves_existing_metadata(tmp_path: Path, monkeypatch) -> None:
    registry_file = tmp_path / "registry.json"
    monkeypatch.setattr(registry, "REGISTRY_FILE", registry_file)

    registry.save_registry([registry.RepoEntry(path="/a", remote_url="git@x:a.git")])

    merged = registry.merge_scanned_paths(["/a", "/b"])

    by_path = {e.path: e for e in merged}
    assert by_path["/a"].remote_url == "git@x:a.git"
    assert by_path["/b"].remote_url is None
