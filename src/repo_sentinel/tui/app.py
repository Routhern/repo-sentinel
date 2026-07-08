"""추적 대시보드 TUI 진입점.

실제 화면 구현은 전부 `tui/screens.py`에 있다. 이 모듈은 `RepoSentinelApp`을
정의하고 최초 화면(`MainMenuScreen`)을 띄우기만 한다.
"""

from __future__ import annotations

from textual.app import App

from repo_sentinel.tui.screens import MainMenuScreen


class RepoSentinelApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "repo-sentinel"

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


def run() -> None:
    RepoSentinelApp().run()
