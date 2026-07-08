from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, OptionList, RichLog

from repo_sentinel.core import tracking
from repo_sentinel.core.config import Config
from repo_sentinel.tui import screens as screens_module
from repo_sentinel.tui.app import RepoSentinelApp
from repo_sentinel.tui.screens import (
    ManageScreen,
    MainMenuScreen,
    PickScreen,
    RelinkScreen,
    RepoDetailScreen,
    SettingsScreen,
    TrackScreen,
    UntrackScreen,
)


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(tracking, "TRACKED_FILE", tmp_path / "tracked.json")
    vault_root = tmp_path / "vault"
    monkeypatch.setattr(screens_module, "load_config", lambda: Config(vault_root=str(vault_root)))
    return tmp_path


def _log_text(log: RichLog) -> str:
    return "\n".join(str(line) for line in log.lines)


async def test_dashboard_starts_at_main_menu(isolated_env: Path) -> None:
    app = RepoSentinelApp()
    async with app.run_test():
        assert isinstance(app.screen, MainMenuScreen)


@pytest.mark.parametrize(
    ("key", "screen_cls"),
    [
        ("1", TrackScreen),
        ("2", UntrackScreen),
        ("3", RelinkScreen),
        ("4", ManageScreen),
        ("5", PickScreen),
        ("6", SettingsScreen),
    ],
)
async def test_number_keys_open_expected_screen(isolated_env: Path, key: str, screen_cls) -> None:
    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press(key)
        await pilot.pause()
        assert isinstance(app.screen, screen_cls)


async def test_escape_returns_to_main_menu(isolated_env: Path) -> None:
    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("1")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)


async def test_q_quits_the_app(isolated_env: Path) -> None:
    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert app.is_running is False


async def test_track_screen_registers_repo(isolated_env: Path) -> None:
    repo = isolated_env / "apple-seed-factory"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("1")
        await pilot.pause()
        app.screen.query_one("#track-path", Input).value = str(repo)
        await pilot.click("#track-submit")
        await pilot.pause()

        assert list(tracking.load_tracked().keys()) == ["apple-seed-factory"]
        assert "추적 완료" in _log_text(app.screen.query_one("#track-log", RichLog))


async def test_track_screen_with_custom_key(isolated_env: Path) -> None:
    repo = isolated_env / "some-very-long-clone-folder-name"
    (repo / ".git").mkdir(parents=True)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("1")
        await pilot.pause()
        app.screen.query_one("#track-path", Input).value = str(repo)
        app.screen.query_one("#track-key", Input).value = "short"
        await pilot.click("#track-submit")
        await pilot.pause()

        assert list(tracking.load_tracked().keys()) == ["short"]


async def test_track_screen_rejects_non_git_directory(isolated_env: Path) -> None:
    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("1")
        await pilot.pause()
        app.screen.query_one("#track-path", Input).value = str(isolated_env / "not-a-repo")
        await pilot.click("#track-submit")
        await pilot.pause()

        assert tracking.load_tracked() == {}
        assert "git 저장소가 아닙니다" in _log_text(app.screen.query_one("#track-log", RichLog))


async def test_untrack_screen_restore_mode_removes_entry(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()
        option_list = app.screen.query_one("#untrack-repo-list", OptionList)
        option_list.highlighted = option_list.get_option_index("repo-a")
        await pilot.click("#untrack-submit")
        await pilot.pause()

        assert tracking.load_tracked() == {}


async def test_untrack_screen_purge_requires_confirmation(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()
        option_list = app.screen.query_one("#untrack-repo-list", OptionList)
        option_list.highlighted = option_list.get_option_index("repo-a")
        app.screen.query_one("#mode-purge").value = True
        await pilot.pause()
        await pilot.click("#untrack-submit")
        await pilot.pause()

        assert type(app.screen).__name__ == "ConfirmModal"
        # 아직 실행 전이므로 추적은 그대로 남아있어야 한다.
        assert "repo-a" in tracking.load_tracked()

        await pilot.click("#confirm-yes")
        await pilot.pause()

        assert tracking.load_tracked() == {}


async def test_untrack_screen_purge_cancelled_keeps_entry(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()
        option_list = app.screen.query_one("#untrack-repo-list", OptionList)
        option_list.highlighted = option_list.get_option_index("repo-a")
        app.screen.query_one("#mode-purge").value = True
        await pilot.pause()
        await pilot.click("#untrack-submit")
        await pilot.pause()
        await pilot.click("#confirm-no")
        await pilot.pause()

        assert "repo-a" in tracking.load_tracked()


async def test_relink_screen_all_target_reports_per_repo(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause()
        option_list = app.screen.query_one("#relink-repo-list", OptionList)
        option_list.highlighted = option_list.get_option_index("__all__")
        await pilot.click("#relink-submit")
        await pilot.pause()

        assert "repo-a" in _log_text(app.screen.query_one("#relink-log", RichLog))


async def test_manage_screen_lists_repos_and_drills_into_detail(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("4")
        await pilot.pause()
        table = app.screen.query_one("#manage-table", DataTable)
        assert table.row_count == 1

        table.focus()
        await pilot.pause()
        table.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, RepoDetailScreen)
        assert app.screen.repo_key == "repo-a"


async def test_repo_detail_untrack_button_opens_preselected_untrack_screen(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        app.push_screen(RepoDetailScreen("repo-a"))
        await pilot.pause()
        await pilot.click("#detail-untrack")
        await pilot.pause()

        assert isinstance(app.screen, UntrackScreen)
        option_list = app.screen.query_one("#untrack-repo-list", OptionList)
        assert option_list.highlighted == option_list.get_option_index("repo-a")


async def test_pick_screen_selects_repo_then_shows_path_form(isolated_env: Path) -> None:
    repo = isolated_env / "repo-a"
    repo.mkdir()
    tracking.add_tracked(repo_key="repo-a", path=str(repo), remote_url=None, is_portable=False)

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("5")
        await pilot.pause()
        option_list = app.screen.query_one("#pick-repo-list", OptionList)
        option_list.highlighted = option_list.get_option_index("repo-a")
        await pilot.press("enter")
        await pilot.pause()

        assert app.screen.query_one("#pick-path", Input) is not None


async def test_settings_screen_saves_parsed_config(isolated_env: Path, monkeypatch) -> None:
    saved: dict[str, Config] = {}
    monkeypatch.setattr(screens_module, "save_config", lambda cfg: saved.update(config=cfg))

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("6")
        await pilot.pause()
        app.screen.query_one("#settings-vault-root", Input).value = str(isolated_env / "new-vault")
        app.screen.query_one("#settings-sync-target", Input).value = str(isolated_env / "nas")
        app.screen.query_one("#settings-patterns", Input).value = ".env, *.env, secret.*"
        await pilot.click("#settings-save")
        await pilot.pause()

    assert saved["config"].vault_root == str(isolated_env / "new-vault")
    assert saved["config"].sync_target == str(isolated_env / "nas")
    assert saved["config"].sensitive_patterns == [".env", "*.env", "secret.*"]


async def test_settings_screen_rejects_empty_vault_root(isolated_env: Path, monkeypatch) -> None:
    saved: dict[str, Config] = {}
    monkeypatch.setattr(screens_module, "save_config", lambda cfg: saved.update(config=cfg))

    app = RepoSentinelApp()
    async with app.run_test() as pilot:
        await pilot.press("6")
        await pilot.pause()
        app.screen.query_one("#settings-vault-root", Input).value = ""
        await pilot.click("#settings-save")
        await pilot.pause()

        assert saved == {}
        assert "비울 수 없습니다" in _log_text(app.screen.query_one("#settings-log", RichLog))
