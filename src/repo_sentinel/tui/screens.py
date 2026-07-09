"""번호 메뉴 기반 화면들.

`RepoSentinelApp`은 `MainMenuScreen`만 띄우고, 나머지 화면은 전부 여기서
`push_screen`/`pop_screen`으로 오간다. CLI와 마찬가지로 각 화면은 `core/*`를
직접 호출할 뿐 새 정책 로직을 만들지 않는다 (CLAUDE.md의 "CLI/TUI가 core를
공유" 원칙).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.suggester import Suggester
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    OptionList,
    RadioButton,
    RadioSet,
    RichLog,
    Rule,
    Static,
)
from textual.widgets.option_list import Option

from repo_sentinel.core import audit as audit_core
from repo_sentinel.core import gitignore as gitignore_core
from repo_sentinel.core import protect as protect_core
from repo_sentinel.core import sync as sync_core
from repo_sentinel.core import tracking
from repo_sentinel.core.config import Config, load_config, save_config
from repo_sentinel.tui.paths import relative_path_candidates


def git_status(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "알 수 없음"
    return "clean" if not result.stdout.strip() else "dirty"


def _repo_option_list(
    tracked: dict[str, tracking.TrackedRepo], *, id: str, include_all: bool = False
) -> OptionList:
    options: list[Option] = []
    if include_all:
        options.append(Option("(전체)", id="__all__"))
    for repo_key, entry in tracked.items():
        options.append(Option(f"{repo_key}  [{entry.path}]", id=repo_key))
    return OptionList(*options, id=id)


class NavScreen(Screen):
    """`Esc`로 이전 화면으로 돌아갈 수 있는 하위 화면들의 공통 베이스."""

    BINDINGS = [Binding("escape", "back", "뒤로", show=True)]

    def action_back(self) -> None:
        self.app.pop_screen()


class ConfirmModal(ModalScreen[bool]):
    """`purge`처럼 되돌릴 수 없는 작업 전에 띄우는 확인 대화상자."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._message, id="confirm-message"),
            Horizontal(
                Button("확인", id="confirm-yes", variant="error"),
                Button("취소", id="confirm-no"),
            ),
            id="confirm-box",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")


MENU_ITEMS: list[tuple[str, str]] = [
    ("1", "레포지토리 Track"),
    ("2", "레포지토리 Untrack"),
    ("3", "레포지토리 Relink"),
    ("4", "레포지토리 관리"),
    ("5", "파일 Pick"),
    ("6", "환경설정"),
]


class MainMenuScreen(Screen):
    BINDINGS = [
        Binding("1", "open_menu('1')", "Track"),
        Binding("2", "open_menu('2')", "Untrack"),
        Binding("3", "open_menu('3')", "Relink"),
        Binding("4", "open_menu('4')", "관리"),
        Binding("5", "open_menu('5')", "Pick"),
        Binding("6", "open_menu('6')", "환경설정"),
        Binding("q", "quit_app", "종료"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("Repo Sentinel 메인 메뉴", classes="screen-title")
        yield Static("숫자 키 또는 방향키+Enter로 선택 · q로 종료", id="menu-hint")
        yield ListView(
            *[ListItem(Label(f"{num}. {label}"), id=f"menu-{num}") for num, label in MENU_ITEMS],
            id="menu-list",
        )
        yield Rule(id="menu-rule")
        yield Static("Q. 종료", id="menu-quit-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#menu-list", ListView).focus()

    def action_open_menu(self, num: str) -> None:
        self._activate(num)

    def action_quit_app(self) -> None:
        self.app.exit()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id:
            self._activate(event.item.id.removeprefix("menu-"))

    def _activate(self, num: str) -> None:
        screen_cls = {
            "1": TrackScreen,
            "2": UntrackScreen,
            "3": RelinkScreen,
            "4": ManageScreen,
            "5": PickScreen,
            "6": SettingsScreen,
        }.get(num)
        if screen_cls is not None:
            self.app.push_screen(screen_cls())


class TrackScreen(NavScreen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("레포지토리 Track", classes="screen-title")
        yield Static("추적할 git 저장소 경로", classes="field-label")
        yield Input(placeholder=r"예: D:\Gitea\myFirstRepo", id="track-path")
        yield Static("repo_key 별칭 (선택, 비우면 remote 기반 기본값 사용)", classes="field-label")
        yield Input(placeholder="예: myrepo", id="track-key")
        yield Horizontal(
            Button("추적하기", id="track-submit", variant="success"),
            Button("뒤로", id="track-back"),
        )
        yield RichLog(id="track-log", wrap=True)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "track-back":
            self.app.pop_screen()
        elif event.button.id == "track-submit":
            self._submit()

    def _submit(self) -> None:
        log = self.query_one("#track-log", RichLog)
        path_input = self.query_one("#track-path", Input)
        key_input = self.query_one("#track-key", Input)
        path_value = path_input.value.strip()
        key_value = key_input.value.strip() or None
        if not path_value:
            log.write(Text("경로를 입력하세요.", style="bold red"))
            return

        result = tracking.track_repo(Path(path_value).resolve(), key_value)
        if result.error:
            log.write(Text(result.error, style="bold red"))
            return
        if result.warning:
            log.write(Text(result.warning, style="yellow"))
        assert result.entry is not None
        log.write(Text(f"추적 완료: {result.entry.repo_key} -> {result.entry.path}", style="bold green"))
        path_input.value = ""
        key_input.value = ""

        if result.gitignore_region_created:
            log.write(
                Text(
                    ".gitignore에 repo-sentinel 리전을 추가했습니다. "
                    "pick 후보 패턴을 바꾸려면 그 구간을 직접 편집하세요 (자동으로 갱신되지 않습니다).",
                    style="white",
                )
            )

        if result.pick_candidates:
            config = load_config()
            vault_root = Path(config.vault_root)
            self._offer_pick_candidates(
                result.entry.repo_key, Path(result.entry.path), vault_root, list(result.pick_candidates)
            )

    def _offer_pick_candidates(
        self, repo_key: str, repo_path: Path, vault_root: Path, candidates: list[str]
    ) -> None:
        if not candidates:
            return
        relative_path, *rest = candidates
        self.app.push_screen(
            ConfirmModal(f"pick 후보: {relative_path}\n지금 pick할까요?"),
            lambda confirmed: self._handle_pick_choice(
                confirmed, repo_key, repo_path, relative_path, vault_root, rest
            ),
        )

    def _handle_pick_choice(
        self,
        confirmed: bool,
        repo_key: str,
        repo_path: Path,
        relative_path: str,
        vault_root: Path,
        rest: list[str],
    ) -> None:
        if confirmed:
            log = self.query_one("#track-log", RichLog)
            try:
                vault_file = protect_core.protect_file(repo_path, relative_path, vault_root, repo_key)
            except (
                FileNotFoundError,
                protect_core.AlreadyProtectedError,
                protect_core.SymlinkPermissionError,
            ) as e:
                log.write(Text(f"{relative_path}: {e}", style="bold red"))
            else:
                log.write(Text(f"격리 완료: {relative_path} -> {vault_file}", style="bold green"))
                added = protect_core.reflect_gitignore(
                    repo_path, repo_key, relative_path, vault_root, should_add=True
                )
                if added:
                    log.write(Text(f".gitignore에 {relative_path}를 자동으로 추가했습니다.", style="white"))
        self._offer_pick_candidates(repo_key, repo_path, vault_root, rest)


class UntrackScreen(NavScreen):
    def __init__(self, repo_key: str | None = None) -> None:
        super().__init__()
        self._preselected_key = repo_key

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("레포지토리 Untrack", classes="screen-title")
        tracked = tracking.load_tracked()
        if not tracked:
            yield Static("추적 중인 레포가 없습니다.")
        else:
            yield Static("해제할 레포 선택", classes="field-label")
            yield _repo_option_list(tracked, id="untrack-repo-list")
            yield Static("해제 방식", classes="field-label")
            yield RadioSet(
                RadioButton("restore — vault 파일을 레포로 복원 (권장)", True, id="mode-restore"),
                RadioButton("keep — 추적만 해제, vault 보존", id="mode-keep"),
                RadioButton("purge — vault 데이터 즉시 삭제", id="mode-purge"),
                id="untrack-mode",
            )
            yield Horizontal(
                Button("해제하기", id="untrack-submit", variant="error"),
                Button("뒤로", id="untrack-back"),
            )
        yield RichLog(id="untrack-log", wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        if not self._preselected_key:
            return
        option_list = self.query_one("#untrack-repo-list", OptionList)
        index = option_list.get_option_index(self._preselected_key)
        option_list.highlighted = index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "untrack-back":
            self.app.pop_screen()
        elif event.button.id == "untrack-submit":
            self._submit()

    def _selected_repo_key(self) -> str | None:
        option_list = self.query_one("#untrack-repo-list", OptionList)
        if option_list.highlighted is None:
            return None
        option = option_list.get_option_at_index(option_list.highlighted)
        return option.id

    def _selected_mode(self) -> str:
        radio_set = self.query_one("#untrack-mode", RadioSet)
        pressed = radio_set.pressed_button
        if pressed is None or pressed.id is None:
            return "restore"
        return pressed.id.removeprefix("mode-")

    def _submit(self) -> None:
        log = self.query_one("#untrack-log", RichLog)
        repo_key = self._selected_repo_key()
        if repo_key is None:
            log.write(Text("해제할 레포를 선택하세요.", style="bold red"))
            return
        mode = self._selected_mode()
        if mode == "purge":
            self.app.push_screen(
                ConfirmModal(
                    "vault 데이터를 즉시 삭제합니다. 레포에는 깨진 심볼릭 링크가 남을 수 있습니다. "
                    "계속할까요?"
                ),
                lambda confirmed: self._do_untrack(repo_key, mode) if confirmed else None,
            )
        else:
            self._do_untrack(repo_key, mode)

    def _do_untrack(self, repo_key: str, mode: str) -> None:
        log = self.query_one("#untrack-log", RichLog)
        config = load_config()
        result = tracking.untrack_repo(repo_key, mode, Path(config.vault_root))
        log.write(Text(result.message, style="bold green" if result.ok else "bold red"))


class RelinkScreen(NavScreen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("레포지토리 Relink", classes="screen-title")
        tracked = tracking.load_tracked()
        if not tracked:
            yield Static("추적 중인 레포가 없습니다.")
        else:
            yield Static("재연결할 대상 선택", classes="field-label")
            yield _repo_option_list(tracked, id="relink-repo-list", include_all=True)
            yield Horizontal(
                Button("재연결 실행", id="relink-submit", variant="success"),
                Button("뒤로", id="relink-back"),
            )
        yield RichLog(id="relink-log", wrap=True)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "relink-back":
            self.app.pop_screen()
        elif event.button.id == "relink-submit":
            self._submit()

    def _submit(self) -> None:
        log = self.query_one("#relink-log", RichLog)
        option_list = self.query_one("#relink-repo-list", OptionList)
        if option_list.highlighted is None:
            log.write(Text("대상을 선택하세요.", style="bold red"))
            return
        option = option_list.get_option_at_index(option_list.highlighted)

        tracked = tracking.load_tracked()
        targets = list(tracked.values()) if option.id == "__all__" else [tracked[option.id]]

        config = load_config()
        vault_root = Path(config.vault_root)
        for entry in targets:
            self._relink_one(entry, vault_root, log)

    @staticmethod
    def _relink_one(entry: tracking.TrackedRepo, vault_root: Path, log: RichLog) -> None:
        try:
            relinked = protect_core.relink_repo(Path(entry.path), entry.repo_key, vault_root)
        except protect_core.DriftError as e:
            log.write(Text(f"{entry.repo_key}: {e}", style="yellow"))
            return
        if relinked:
            log.write(Text(f"{entry.repo_key}: {', '.join(relinked)} 재연결", style="bold green"))
        else:
            log.write(Text(f"{entry.repo_key}: 변경 없음", style="white"))


class ManageScreen(NavScreen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("레포지토리 관리", classes="screen-title")
        yield Horizontal(
            Button("Sync Push", id="manage-sync-push"),
            Button("Sync Pull", id="manage-sync-pull"),
        )
        yield DataTable(id="manage-table")
        yield RichLog(id="manage-log", wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#manage-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("repo_key", "경로", "git", "이슈")
        self.refresh_table()

    def on_screen_resume(self) -> None:
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one("#manage-table", DataTable)
        table.clear()
        config = load_config()
        vault_root = Path(config.vault_root)
        for repo_key, entry in tracking.load_tracked().items():
            state = git_status(entry.path)
            state_text = Text(state, style="bold green" if state == "clean" else "bold yellow")
            issues = audit_core.audit_repo(Path(entry.path), repo_key, vault_root)
            issue_text = Text(str(len(issues)), style="bold red" if issues else "white")
            table.add_row(repo_key, entry.path, state_text, issue_text, key=repo_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id not in {"manage-sync-push", "manage-sync-pull"}:
            return
        log = self.query_one("#manage-log", RichLog)
        config = load_config()
        if not config.sync_target:
            log.write(Text("sync_target이 설정되지 않았습니다. 환경설정에서 지정하세요.", style="bold red"))
            return

        vault_root = Path(config.vault_root)
        sync_target = Path(config.sync_target)
        if event.button.id == "manage-sync-push":
            copied = sync_core.push_to_sync_target(vault_root, sync_target)
        else:
            copied = sync_core.pull_from_sync_target(vault_root, sync_target)
        if copied:
            log.write(Text(f"{len(copied)}개 파일 동기화: " + ", ".join(copied), style="bold green"))
        else:
            log.write(Text("변경된 파일이 없습니다.", style="white"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        repo_key = event.row_key.value
        if repo_key:
            self.app.push_screen(RepoDetailScreen(repo_key))


class RepoDetailScreen(NavScreen):
    def __init__(self, repo_key: str) -> None:
        super().__init__()
        self.repo_key = repo_key

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(f"레포지토리 상세 — {self.repo_key}", classes="screen-title")
        yield Static(id="detail-info")
        yield Horizontal(
            Button("Audit 새로고침", id="detail-audit"),
            Button("Relink", id="detail-relink"),
            Button("Pick 파일 추가", id="detail-pick"),
            Button("Untrack", id="detail-untrack", variant="error"),
        )
        yield RichLog(id="detail-log", wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_info()

    def on_screen_resume(self) -> None:
        self._refresh_info()

    def _entry(self) -> tracking.TrackedRepo | None:
        return tracking.load_tracked().get(self.repo_key)

    def _refresh_info(self) -> None:
        info = self.query_one("#detail-info", Static)
        log = self.query_one("#detail-log", RichLog)
        entry = self._entry()
        if entry is None:
            info.update("이 레포는 더 이상 추적되지 않습니다.")
            return

        config = load_config()
        vault_root = Path(config.vault_root)
        issues = audit_core.audit_repo(Path(entry.path), self.repo_key, vault_root)
        info.update(
            "\n".join(
                [
                    f"경로: {entry.path}",
                    f"remote: {entry.remote_url or '-'}",
                    f"git 상태: {git_status(entry.path)}",
                    f"이슈: {len(issues)}건",
                ]
            )
        )
        log.clear()
        if issues:
            for issue in issues:
                log.write(Text(f"[{issue.kind}] {issue.relative_path}: {issue.detail}", style="bold red"))
        else:
            log.write(Text("문제 없음.", style="bold green"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "detail-audit":
            self._refresh_info()
        elif event.button.id == "detail-relink":
            self._relink()
        elif event.button.id == "detail-pick":
            self.app.push_screen(PickScreen(repo_key=self.repo_key))
        elif event.button.id == "detail-untrack":
            self.app.push_screen(UntrackScreen(repo_key=self.repo_key))

    def _relink(self) -> None:
        entry = self._entry()
        if entry is None:
            return
        log = self.query_one("#detail-log", RichLog)
        config = load_config()
        vault_root = Path(config.vault_root)
        try:
            relinked = protect_core.relink_repo(Path(entry.path), self.repo_key, vault_root)
        except protect_core.DriftError as e:
            log.write(Text(str(e), style="yellow"))
            return
        if relinked:
            log.write(Text(f"{', '.join(relinked)} 재연결", style="bold green"))
        else:
            log.write(Text("변경 없음", style="white"))
        self._refresh_info()


class RepoPathSuggester(Suggester):
    """PickScreen에서 선택된 레포 안의 상대경로를 접두 매칭으로 완성한다."""

    def __init__(self, repo_path_provider) -> None:
        super().__init__(use_cache=False, case_sensitive=True)
        self._repo_path_provider = repo_path_provider

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        repo_path = self._repo_path_provider()
        if repo_path is None:
            return None
        candidates = relative_path_candidates(repo_path, value)
        return candidates[0] if candidates else None


class PickScreen(NavScreen):
    def __init__(self, repo_key: str | None = None) -> None:
        super().__init__()
        self.repo_key = repo_key

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("파일 Pick", classes="screen-title")
        if self.repo_key is None:
            tracked = tracking.load_tracked()
            if not tracked:
                yield Static("추적 중인 레포가 없습니다.")
            else:
                yield Static("대상 레포 선택", classes="field-label")
                yield _repo_option_list(tracked, id="pick-repo-list")
        else:
            yield Static(f"대상 레포: {self.repo_key}", classes="field-label")
            yield Static("보호할 상대 경로", classes="field-label")
            yield Input(
                placeholder="예: src/input/data.csv",
                id="pick-path",
                suggester=RepoPathSuggester(self._repo_path),
            )
            yield Horizontal(
                Button("추가", id="pick-submit", variant="success"),
                Button("자동 탐지(--auto)", id="pick-auto"),
                Button("뒤로", id="pick-back"),
            )
        yield RichLog(id="pick-log", wrap=True)
        yield Footer()

    def _repo_path(self) -> Path | None:
        entry = tracking.load_tracked().get(self.repo_key) if self.repo_key else None
        return Path(entry.path) if entry else None

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self.repo_key = event.option_id
            await self.recompose()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick-back":
            self.app.pop_screen()
        elif event.button.id == "pick-submit":
            self._submit_one()
        elif event.button.id == "pick-auto":
            self._submit_auto()

    def _submit_one(self) -> None:
        path_input = self.query_one("#pick-path", Input)
        relative_path = path_input.value.strip()
        if not relative_path:
            self.query_one("#pick-log", RichLog).write(Text("경로를 입력하세요.", style="bold red"))
            return
        self._protect_one(relative_path)
        path_input.value = ""

    def _submit_auto(self) -> None:
        entry = tracking.load_tracked().get(self.repo_key) if self.repo_key else None
        if entry is None:
            return
        config = load_config()
        patterns = gitignore_core.resolve_patterns(Path(entry.path), config.sensitive_patterns)
        candidates = protect_core.find_candidates(Path(entry.path), patterns)
        if not candidates:
            self.query_one("#pick-log", RichLog).write(Text("자동 탐지된 후보가 없습니다.", style="white"))
            return
        for relative_path in candidates:
            self._protect_one(relative_path)

    def _protect_one(self, relative_path: str) -> None:
        log = self.query_one("#pick-log", RichLog)
        entry = tracking.load_tracked().get(self.repo_key) if self.repo_key else None
        if entry is None:
            return
        repo_path = Path(entry.path)
        config = load_config()
        vault_root = Path(config.vault_root)
        try:
            vault_file = protect_core.protect_file(repo_path, relative_path, vault_root, self.repo_key)
        except (FileNotFoundError, protect_core.AlreadyProtectedError, protect_core.SymlinkPermissionError) as e:
            log.write(Text(f"{relative_path}: {e}", style="bold red"))
            return

        log.write(Text(f"격리 완료: {relative_path} -> {vault_file}", style="bold green"))
        added = protect_core.reflect_gitignore(repo_path, self.repo_key, relative_path, vault_root, should_add=True)
        if added:
            log.write(Text(f".gitignore에 {relative_path}를 자동으로 추가했습니다.", style="white"))


class SettingsScreen(NavScreen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("환경설정", classes="screen-title")
        config = load_config()
        yield Static("vault_root", classes="field-label")
        yield Input(value=config.vault_root, id="settings-vault-root")
        yield Static("sync_target (비우면 미설정)", classes="field-label")
        yield Input(value=config.sync_target or "", id="settings-sync-target")
        yield Static("sensitive_patterns (쉼표로 구분)", classes="field-label")
        yield Input(value=", ".join(config.sensitive_patterns), id="settings-patterns")
        yield Horizontal(
            Button("저장", id="settings-save", variant="success"),
            Button("뒤로", id="settings-back"),
        )
        yield RichLog(id="settings-log", wrap=True)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-back":
            self.app.pop_screen()
        elif event.button.id == "settings-save":
            self._save()

    def _save(self) -> None:
        log = self.query_one("#settings-log", RichLog)
        vault_root = self.query_one("#settings-vault-root", Input).value.strip()
        sync_target = self.query_one("#settings-sync-target", Input).value.strip()
        patterns = [p.strip() for p in self.query_one("#settings-patterns", Input).value.split(",") if p.strip()]

        if not vault_root:
            log.write(Text("vault_root는 비울 수 없습니다.", style="bold red"))
            return

        new_config = Config(
            scan_roots=load_config().scan_roots,
            vault_root=vault_root,
            sync_target=sync_target or None,
            sensitive_patterns=patterns,
        )
        save_config(new_config)
        log.write(Text("설정을 저장했습니다.", style="bold green"))
