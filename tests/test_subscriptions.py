from pathlib import Path

from repo_sentinel.core import subscriptions


def test_add_and_load_subscription(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(subscriptions, "SUBSCRIPTIONS_FILE", tmp_path / "subscriptions.json")

    subscriptions.add_subscription(
        repo_key="github.com__me__proj", path="/repos/proj", remote_url="git@github.com:me/proj.git", is_portable=True
    )

    loaded = subscriptions.load_subscriptions()
    assert loaded["github.com__me__proj"].path == "/repos/proj"


def test_remove_subscription(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(subscriptions, "SUBSCRIPTIONS_FILE", tmp_path / "subscriptions.json")
    subscriptions.add_subscription(repo_key="k", path="/p", remote_url=None, is_portable=False)

    removed = subscriptions.remove_subscription("k")

    assert removed is not None
    assert subscriptions.load_subscriptions() == {}
