from pathlib import Path

from repo_sentinel.core import tracking


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
