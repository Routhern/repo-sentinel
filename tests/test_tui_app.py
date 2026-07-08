from pathlib import Path

import pytest
from textual.widgets import DataTable

from repo_sentinel.core import tracking
from repo_sentinel.core.config import Config
from repo_sentinel.tui import app as app_module
from repo_sentinel.tui.app import RepoSentinelApp


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    vault_root = tmp_path / "vault"
    monkeypatch.setattr(app_module, "load_config", lambda: Config(vault_root=str(vault_root)))
    return tmp_path


async def test_dashboard_starts_empty(isolated_env: Path) -> None:
    app = RepoSentinelApp()
    async with app.run_test():
        table = app.query_one("#tracked-table", DataTable)
        assert table.row_count == 0


async def test_track_populates_table(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_track([str(repo)])
        await pilot.pause()

        table = app.query_one("#tracked-table", DataTable)
        assert table.row_count == 1
        assert list(app.tracked.keys()) == ["apple-seed-factory"]


async def test_untrack_removes_from_table(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_track([str(repo)])
        await pilot.pause()
        app._cmd_untrack(["apple-seed-factory", "keep"])
        await pilot.pause()

        table = app.query_one("#tracked-table", DataTable)
        assert table.row_count == 0


async def test_track_with_custom_key(isolated_env: Path) -> None:
    repo = isolated_env / "some-very-long-clone-folder-name"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_track([str(repo), "--key", "short"])
        await pilot.pause()

        assert list(app.tracked.keys()) == ["short"]


async def test_track_rejects_key_collision_with_different_path(isolated_env: Path) -> None:
    repo_a = isolated_env / "repo-a"
    repo_b = isolated_env / "repo-b"
    (repo_a / ".git").mkdir(parents=True)
    (repo_b / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_track([str(repo_a), "--key", "dup"])
        await pilot.pause()
        app._cmd_track([str(repo_b), "--key", "dup"])
        await pilot.pause()

        assert app.tracked["dup"].path == str(repo_a.resolve())


async def test_suggester_is_wired_to_live_tracked_repos(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app._cmd_track([str(repo)])
        await pilot.pause()

        assert app._repo_keys() == ["apple-seed-factory"]
