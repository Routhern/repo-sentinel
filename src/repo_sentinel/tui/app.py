"""추적 대시보드 TUI. CLI와 동일하게 core/*의 로직만 호출하고, 새 정책 로직은
여기서 만들지 않는다 (CLAUDE.md의 "CLI/TUI가 core를 공유" 원칙).
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, RichLog

from repo_sentinel.core import audit as audit_core
from repo_sentinel.core import protect as protect_core
from repo_sentinel.core import sync as sync_core
from repo_sentinel.core import tracking
from repo_sentinel.core.config import load_config
from repo_sentinel.core.gitignore import add_entry as gitignore_add_entry
from repo_sentinel.core.gitignore import is_ignored
from repo_sentinel.core.repo_key import compute_repo_key
from repo_sentinel.core.vault import load_manifest
from repo_sentinel.tui.paths import relative_path_candidates
from repo_sentinel.tui.suggester import CommandSuggester

HELP_TEXT = (
    "track(t) <경로> [--key 별칭] | untrack(ut) <repo_key> [restore|keep|purge] | "
    "pick(p) <repo_key> <경로...|--auto> | relink [repo_key] | audit [repo_key] | "
    "sync <push|pull> | refresh | quit"
)


def _git_status(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "알 수 없음"
    return "clean" if not result.stdout.strip() else "dirty"


class RepoSentinelApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "repo-sentinel"
    BINDINGS = [
        Binding("q", "quit", "종료"),
        Binding("f5", "refresh_table", "새로고침"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.tracked: dict[str, tracking.TrackedRepo] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(id="tracked-table")
        yield RichLog(id="log", wrap=True)
        yield Input(placeholder=HELP_TEXT, id="command-input", suggester=self._make_suggester())
        yield Footer()

    def _make_suggester(self) -> CommandSuggester:
        return CommandSuggester(self._repo_keys, self._path_candidates)

    def _repo_keys(self) -> list[str]:
        return list(self.tracked.keys())

    def _path_candidates(self, repo_key: str, prefix: str) -> list[str]:
        entry = self.tracked.get(repo_key)
        if entry is None:
            return []
        return relative_path_candidates(Path(entry.path), prefix)

    def on_mount(self) -> None:
        table = self.query_one("#tracked-table", DataTable)
        table.add_columns("repo_key", "경로", "git", "이슈")
        self.refresh_table()
        self.log_info(f"명령을 입력하세요. {HELP_TEXT}")

    def action_refresh_table(self) -> None:
        self.refresh_table()

    def refresh_table(self) -> None:
        self.tracked = tracking.load_tracked()
        config = load_config()
        vault_root = Path(config.vault_root)

        table = self.query_one("#tracked-table", DataTable)
        table.clear()
        for entry in self.tracked.values():
            state = _git_status(entry.path)
            state_text = Text(state, style="bold green" if state == "clean" else "bold yellow")
            issues = audit_core.audit_repo(Path(entry.path), entry.repo_key, vault_root)
            issue_text = Text(str(len(issues)), style="bold red" if issues else "white")
            table.add_row(entry.repo_key, entry.path, state_text, issue_text)

    def log_info(self, message: str) -> None:
        self.query_one("#log", RichLog).write(Text(message, style="white"))

    def log_error(self, message: str) -> None:
        self.query_one("#log", RichLog).write(Text(message, style="bold red"))

    def log_success(self, message: str) -> None:
        self.query_one("#log", RichLog).write(Text(message, style="bold green"))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        event.input.value = ""
        raw = event.value.strip()
        if not raw:
            return
        try:
            tokens = shlex.split(raw)
        except ValueError as e:
            self.log_error(f"입력을 해석할 수 없습니다: {e}")
            return
        if not tokens:
            return

        command, args = tokens[0].lower(), tokens[1:]
        handler = {
            "track": self._cmd_track,
            "t": self._cmd_track,
            "untrack": self._cmd_untrack,
            "ut": self._cmd_untrack,
            "pick": self._cmd_pick,
            "p": self._cmd_pick,
            "relink": self._cmd_relink,
            "audit": self._cmd_audit,
            "sync": self._cmd_sync,
            "refresh": lambda _args: self.refresh_table(),
            "quit": lambda _args: self.exit(),
        }.get(command)

        if handler is None:
            self.log_error(f"알 수 없는 명령입니다: {command}")
            return
        handler(args)

    def _cmd_track(self, args: list[str]) -> None:
        if not args:
            self.log_error("사용법: track <경로> [--key <별칭>]")
            return
        rest = args[1:]
        custom_key: str | None = None
        if rest:
            if rest[0] in ("--key", "-k") and len(rest) > 1:
                custom_key = rest[1]
            else:
                self.log_error("사용법: track <경로> [--key <별칭>]")
                return

        repo_path = Path(args[0]).resolve()
        if not (repo_path / ".git").exists():
            self.log_error(f"{repo_path}는 git 저장소가 아닙니다.")
            return
        result = compute_repo_key(repo_path)
        if custom_key is None and not result.is_portable:
            self.log_error("경고: remote가 없어 폴더 이름을 repo_key로 사용합니다 (다른 머신과 이식 불가).")

        repo_key = custom_key or result.key
        if custom_key:
            self.log_info(
                f"사용자 지정 repo_key를 사용합니다: {repo_key} "
                "(다른 머신에서도 동일한 --key로 track해야 relink가 가능합니다)"
            )

        existing = self.tracked.get(repo_key)
        if existing is not None and Path(existing.path) != repo_path:
            self.log_error(f"repo_key '{repo_key}'는 이미 다른 경로({existing.path})에서 사용 중입니다.")
            return

        entry = tracking.add_tracked(
            repo_key=repo_key, path=str(repo_path), remote_url=result.remote_url, is_portable=result.is_portable
        )
        self.log_success(f"추적 완료: {entry.repo_key} -> {entry.path}")
        self.refresh_table()

    def _cmd_untrack(self, args: list[str]) -> None:
        if not args:
            self.log_error("사용법: untrack <repo_key> [restore|keep|purge]")
            return
        repo_key = args[0]
        mode = args[1] if len(args) > 1 else "restore"
        if mode not in {"restore", "keep", "purge"}:
            self.log_error("mode는 restore, keep, purge 중 하나여야 합니다.")
            return
        entry = self.tracked.get(repo_key)
        if entry is None:
            self.log_error(f"{repo_key}는 추적 중이 아닙니다.")
            return

        config = load_config()
        vault_root = Path(config.vault_root)
        repo_path = Path(entry.path)

        if mode == "purge":
            from repo_sentinel.core.vault import repo_vault_dir

            vault_dir = repo_vault_dir(vault_root, repo_key)
            if vault_dir.exists():
                shutil.rmtree(vault_dir)
        elif mode == "restore":
            manifest = load_manifest(vault_root)
            manifest_entry = manifest.repos.get(repo_key)
            if manifest_entry:
                for protected in list(manifest_entry.files):
                    protect_core.restore_file(
                        repo_path, protected.relative_path, vault_root, repo_key, delete_vault_copy=True
                    )

        tracking.remove_tracked(repo_key)
        self.log_success(f"{repo_key} 추적 해제 완료 (mode={mode})")
        self.refresh_table()

    def _cmd_pick(self, args: list[str]) -> None:
        if not args:
            self.log_error("사용법: pick <repo_key> <경로...> | pick <repo_key> --auto")
            return
        repo_key, rest = args[0], args[1:]
        entry = self.tracked.get(repo_key)
        if entry is None:
            self.log_error(f"{repo_key}는 추적 중이 아닙니다.")
            return

        repo_path = Path(entry.path)
        config = load_config()
        vault_root = Path(config.vault_root)

        target_paths = [p for p in rest if p != "--auto"]
        if "--auto" in rest:
            target_paths.extend(protect_core.find_candidates(repo_path, config.sensitive_patterns))
        target_paths = sorted(set(target_paths))

        if not target_paths:
            self.log_error("보호할 파일이 없습니다.")
            return

        for relative_path in target_paths:
            try:
                vault_file = protect_core.protect_file(repo_path, relative_path, vault_root, repo_key)
            except (
                FileNotFoundError,
                protect_core.AlreadyProtectedError,
                protect_core.SymlinkPermissionError,
            ) as e:
                self.log_error(f"{relative_path}: {e}")
                continue

            self.log_success(f"격리 완료: {relative_path} -> {vault_file}")
            if is_ignored(repo_path, relative_path):
                protect_core.mark_gitignore_verified(vault_root, repo_key, relative_path)
            else:
                gitignore_add_entry(repo_path, relative_path)
                protect_core.mark_gitignore_verified(vault_root, repo_key, relative_path)
                self.log_info(f".gitignore에 {relative_path}를 자동으로 추가했습니다.")
        self.refresh_table()

    def _cmd_relink(self, args: list[str]) -> None:
        config = load_config()
        vault_root = Path(config.vault_root)
        targets = [self.tracked[args[0]]] if args else list(self.tracked.values())
        if args and args[0] not in self.tracked:
            self.log_error(f"{args[0]}는 추적 중이 아닙니다.")
            return

        for entry in targets:
            try:
                relinked = protect_core.relink_repo(Path(entry.path), entry.repo_key, vault_root)
            except protect_core.DriftError as e:
                self.log_error(f"{entry.repo_key}: {e}")
                continue
            if relinked:
                self.log_success(f"{entry.repo_key}: {', '.join(relinked)} 재연결")
            else:
                self.log_info(f"{entry.repo_key}: 변경 없음")
        self.refresh_table()

    def _cmd_audit(self, args: list[str]) -> None:
        config = load_config()
        vault_root = Path(config.vault_root)
        targets = [self.tracked[args[0]]] if args else list(self.tracked.values())
        if args and args[0] not in self.tracked:
            self.log_error(f"{args[0]}는 추적 중이 아닙니다.")
            return

        found_any = False
        for entry in targets:
            for issue in audit_core.audit_repo(Path(entry.path), entry.repo_key, vault_root):
                found_any = True
                self.log_error(f"{issue.repo_key} [{issue.kind}] {issue.relative_path}: {issue.detail}")
        if not found_any:
            self.log_success("문제 없음.")
        self.refresh_table()

    def _cmd_sync(self, args: list[str]) -> None:
        direction = args[0] if args else "push"
        if direction not in {"push", "pull"}:
            self.log_error("사용법: sync <push|pull>")
            return
        config = load_config()
        if not config.sync_target:
            self.log_error("sync_target이 설정되지 않았습니다 (~/.repo-sentinel/config.toml).")
            return
        vault_root, sync_target = Path(config.vault_root), Path(config.sync_target)
        if direction == "push":
            copied = sync_core.push_to_sync_target(vault_root, sync_target)
        else:
            copied = sync_core.pull_from_sync_target(vault_root, sync_target)
        if copied:
            self.log_success(f"{len(copied)}개 파일 동기화: " + ", ".join(copied))
        else:
            self.log_info("변경된 파일이 없습니다.")


def run() -> None:
    RepoSentinelApp().run()
