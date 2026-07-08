from pathlib import Path

import pytest
from textual.widgets import DataTable

from repo_sentinel.core import subscriptions as subs_core
from repo_sentinel.core.config import Config
from repo_sentinel.tui import app as app_module
from repo_sentinel.tui.app import RepoSentinelApp


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(subs_core, "SUBSCRIPTIONS_FILE", tmp_path / "subscriptions.json")
    vault_root = tmp_path / "vault"
    monkeypatch.setattr(app_module, "load_config", lambda: Config(vault_root=str(vault_root)))
    return tmp_path


async def test_dashboard_starts_empty(isolated_env: Path) -> None:
    app = RepoSentinelApp()
    async with app.run_test():
        table = app.query_one("#subscriptions-table", DataTable)
        assert table.row_count == 0


async def test_subscribe_populates_table(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_subscribe([str(repo)])
        await pilot.pause()

        table = app.query_one("#subscriptions-table", DataTable)
        assert table.row_count == 1
        assert list(app.subscriptions.keys()) == ["apple-seed-factory"]


async def test_unsubscribe_removes_from_table(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_subscribe([str(repo)])
        await pilot.pause()
        app._cmd_unsubscribe(["apple-seed-factory", "keep"])
        await pilot.pause()

        table = app.query_one("#subscriptions-table", DataTable)
        assert table.row_count == 0


async def test_suggester_is_wired_to_live_subscriptions(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_subscribe([str(repo)])
        await pilot.pause()

        assert app._repo_keys() == ["apple-seed-factory"]
