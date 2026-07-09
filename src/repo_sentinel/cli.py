from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from repo_sentinel.core import audit as audit_core
from repo_sentinel.core import gitignore as gitignore_core
from repo_sentinel.core import protect as protect_core
from repo_sentinel.core import scanner, sync as sync_core, tracking
from repo_sentinel.core.config import load_config, save_config
from repo_sentinel.core.gitignore import is_ignored

app = typer.Typer(help="PC 전역의 git 저장소를 관리하는 repo-sentinel CLI")
console = Console()


@app.command()
def scan(root: Path = typer.Argument(Path.home(), help="탐색을 시작할 루트 디렉터리")) -> None:
    """ROOT 이하에서 git 저장소를 찾아 보여준다 (읽기 전용, 아무것도 등록하지 않는다)."""
    found = scanner.find_git_repos(root)
    if not found:
        console.print("git 저장소를 찾지 못했습니다.")
        raise typer.Exit()

    table = Table(title=f"{root} 이하에서 발견된 저장소")
    table.add_column("경로")
    for path in found:
        table.add_row(str(path))
    console.print(table)
    console.print(f"[dim]추적하려면 `repo-sentinel track <경로>`를 실행하세요.[/dim]")


@app.command(name="track")
def track(
    path: Path = typer.Argument(..., help="추적할 git 저장소 경로"),
    key: Optional[str] = typer.Option(
        None,
        "--key",
        "-k",
        help="repo_key로 쓸 짧은 별칭 (생략 시 remote URL 기반의 긴 기본값을 사용)",
    ),
) -> None:
    """PATH를 추적 목록에 등록한다. 이때부터 pick/relink/audit 대상이 된다."""
    repo_path = path.resolve()
    result = tracking.track_repo(repo_path, key)
    if result.error:
        console.print(f"[red]{result.error}[/red]")
        raise typer.Exit(code=1)

    if result.warning:
        style = "yellow" if key is None else "dim"
        prefix = "경고: " if key is None else ""
        console.print(f"[{style}]{prefix}{result.warning}[/{style}]")

    entry = result.entry
    assert entry is not None
    console.print(f"[green]추적 완료[/green]: {entry.repo_key} -> {entry.path}")

    if result.gitignore_region_created:
        console.print(
            "[dim].gitignore에 repo-sentinel 리전을 추가했습니다. "
            "pick 후보 패턴을 바꾸려면 그 구간을 직접 편집하세요 (자동으로 갱신되지 않습니다).[/dim]"
        )

    if result.pick_candidates:
        config = load_config()
        vault_root = Path(config.vault_root)
        console.print(f"[cyan]pick 후보 파일 {len(result.pick_candidates)}개를 찾았습니다.[/cyan]")
        for relative_path in result.pick_candidates:
            if typer.confirm(f"{relative_path}를 지금 pick할까요?", default=True):
                _pick_one(repo_path, entry.repo_key, relative_path, vault_root)


app.command(name="t")(track)


@app.command(name="untrack")
def untrack(
    repo_key: str = typer.Argument(..., help="추적 해제할 repo_key"),
    mode: str = typer.Option(
        "restore",
        help="restore: vault 파일을 레포로 복원 후 해제(권장) / "
        "keep: 추적만 해제하고 vault 데이터는 보존 / "
        "purge: vault 데이터까지 즉시 삭제(레포에 깨진 링크가 남을 수 있음)",
    ),
) -> None:
    """추적을 해제한다. 보호 중이던 파일 처리 방식은 --mode로 선택한다."""
    if mode not in {"restore", "keep", "purge"}:
        console.print("[red]--mode는 restore, keep, purge 중 하나여야 합니다.[/red]")
        raise typer.Exit(code=1)

    if repo_key not in tracking.load_tracked():
        console.print(f"[red]{repo_key}는 추적 중이 아닙니다.[/red]")
        raise typer.Exit(code=1)

    if mode == "purge":
        confirmed = typer.confirm(
            "vault 데이터를 즉시 삭제합니다. 레포에는 깨진 심볼릭 링크가 남을 수 있습니다. 계속할까요?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit()

    config = load_config()
    vault_root = Path(config.vault_root)
    result = tracking.untrack_repo(repo_key, mode, vault_root)
    console.print(f"[green]{result.message}[/green]")


app.command(name="ut")(untrack)


@app.command(name="list")
def list_repos() -> None:
    """추적 중인 저장소 목록을 출력한다."""
    tracked = tracking.load_tracked()
    if not tracked:
        console.print("추적 중인 저장소가 없습니다. 먼저 `repo-sentinel track`을 실행하세요.")
        raise typer.Exit()

    table = Table(title="repo-sentinel tracked repos")
    table.add_column("repo_key")
    table.add_column("경로")
    table.add_column("원격 URL")
    for entry in tracked.values():
        table.add_row(entry.repo_key, entry.path, entry.remote_url or "-")
    console.print(table)


@app.command()
def status() -> None:
    """추적 중인 각 저장소의 git 상태(dirty 여부)를 요약한다."""
    tracked = tracking.load_tracked()
    if not tracked:
        console.print("추적 중인 저장소가 없습니다. 먼저 `repo-sentinel track`을 실행하세요.")
        raise typer.Exit()

    table = Table(title="repo status")
    table.add_column("repo_key")
    table.add_column("상태")
    for entry in tracked.values():
        result = subprocess.run(
            ["git", "-C", entry.path, "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        state = "clean" if result.returncode == 0 and not result.stdout.strip() else "dirty"
        table.add_row(entry.repo_key, state)
    console.print(table)


def _confirm_gitignore_add(repo_path: Path, relative_path: str) -> bool:
    """이미 무시되어 있으면 물어볼 필요가 없으므로 바로 True, 아니면 사용자에게 확인한다."""
    if is_ignored(repo_path, relative_path):
        return True
    return typer.confirm(
        f".gitignore에 {relative_path}가 없습니다. 지금 추가할까요? "
        "(추가하지 않으면 심볼릭 링크가 그대로 커밋될 수 있습니다)",
        default=True,
    )


def _pick_one(repo_path: Path, repo_key: str, relative_path: str, vault_root: Path) -> None:
    """protect_file 실행 + .gitignore 반영까지 한 번에 처리한다. `pick`과 `track`이 공유한다."""
    try:
        vault_file = protect_core.protect_file(repo_path, relative_path, vault_root, repo_key)
    except (FileNotFoundError, protect_core.AlreadyProtectedError, protect_core.SymlinkPermissionError) as e:
        console.print(f"[red]{relative_path}: {e}[/red]")
        return

    console.print(f"[green]격리 완료[/green]: {relative_path} -> {vault_file}")
    should_add = _confirm_gitignore_add(repo_path, relative_path)
    protect_core.reflect_gitignore(repo_path, repo_key, relative_path, vault_root, should_add=should_add)


@app.command(name="pick")
def pick(
    repo_key: str = typer.Argument(..., help="대상 repo_key"),
    paths: Optional[list[str]] = typer.Argument(None, help="보호할 레포 내 상대경로 (생략 시 --auto 필요)"),
    auto: bool = typer.Option(
        False, "--auto", help="레포의 .gitignore 리전(없으면 전역 sensitive_patterns)으로 후보를 자동 탐색"
    ),
) -> None:
    """레포의 지정 파일을 vault로 옮기고 심볼릭 링크로 대체한다."""
    tracked = tracking.load_tracked()
    entry = tracked.get(repo_key)
    if entry is None:
        console.print(f"[red]{repo_key}는 추적 중이 아닙니다. 먼저 track하세요.[/red]")
        raise typer.Exit(code=1)

    repo_path = Path(entry.path)
    config = load_config()
    vault_root = Path(config.vault_root)

    target_paths = list(paths or [])
    if auto:
        patterns = gitignore_core.resolve_patterns(repo_path, config.sensitive_patterns)
        target_paths.extend(protect_core.find_candidates(repo_path, patterns))
    target_paths = sorted(set(target_paths))

    if not target_paths:
        console.print("보호할 파일이 없습니다. 경로를 지정하거나 --auto를 사용하세요.")
        raise typer.Exit()

    for relative_path in target_paths:
        _pick_one(repo_path, repo_key, relative_path, vault_root)


app.command(name="p")(pick)


@app.command()
def relink(repo_key: Optional[str] = typer.Argument(None, help="생략 시 추적 중인 전체를 재연결")) -> None:
    """매니페스트 기준으로 현재 머신의 심볼릭 링크를 재생성한다."""
    tracked = tracking.load_tracked()
    config = load_config()
    vault_root = Path(config.vault_root)

    targets = [tracked[repo_key]] if repo_key else list(tracked.values())
    if repo_key and repo_key not in tracked:
        console.print(f"[red]{repo_key}는 추적 중이 아닙니다.[/red]")
        raise typer.Exit(code=1)

    for entry in targets:
        try:
            relinked = protect_core.relink_repo(Path(entry.path), entry.repo_key, vault_root)
        except protect_core.DriftError as e:
            console.print(f"[yellow]{entry.repo_key}: {e}[/yellow]")
            continue
        if relinked:
            console.print(f"[green]{entry.repo_key}[/green]: {', '.join(relinked)} 재연결")
        else:
            console.print(f"{entry.repo_key}: 변경 없음")


@app.command()
def audit(repo_key: Optional[str] = typer.Argument(None, help="생략 시 추적 중인 전체를 점검")) -> None:
    """보호 중인 파일들의 무결성(깨진 링크, gitignore 반영, 드리프트)을 점검한다."""
    tracked = tracking.load_tracked()
    config = load_config()
    vault_root = Path(config.vault_root)

    targets = [tracked[repo_key]] if repo_key else list(tracked.values())
    if repo_key and repo_key not in tracked:
        console.print(f"[red]{repo_key}는 추적 중이 아닙니다.[/red]")
        raise typer.Exit(code=1)

    all_issues = []
    for entry in targets:
        all_issues.extend(audit_core.audit_repo(Path(entry.path), entry.repo_key, vault_root))

    if not all_issues:
        console.print("[green]문제 없음.[/green]")
        raise typer.Exit()

    table = Table(title="audit 결과")
    table.add_column("repo_key")
    table.add_column("경로")
    table.add_column("종류")
    table.add_column("설명")
    for issue in all_issues:
        table.add_row(issue.repo_key, issue.relative_path, issue.kind, issue.detail)
    console.print(table)
    raise typer.Exit(code=1)


@app.command()
def sync(
    direction: str = typer.Option("push", help="push: vault_root -> sync_target / pull: 반대 방향"),
) -> None:
    """vault_root와 sync_target 사이를 미러링한다."""
    if direction not in {"push", "pull"}:
        console.print("[red]--direction은 push 또는 pull이어야 합니다.[/red]")
        raise typer.Exit(code=1)

    config = load_config()
    if not config.sync_target:
        console.print("[red]sync_target이 설정되지 않았습니다 (~/.repo-sentinel/config.toml).[/red]")
        raise typer.Exit(code=1)

    vault_root = Path(config.vault_root)
    sync_target = Path(config.sync_target)
    if direction == "push":
        copied = sync_core.push_to_sync_target(vault_root, sync_target)
    else:
        copied = sync_core.pull_from_sync_target(vault_root, sync_target)

    if copied:
        console.print(f"[green]{len(copied)}개 파일 동기화[/green]: " + ", ".join(copied))
    else:
        console.print("변경된 파일이 없습니다.")


@app.command(name="set-vault-root")
def set_vault_root(path: Path = typer.Argument(..., help="vault로 사용할 로컬 디렉터리")) -> None:
    """vault_root 경로를 설정한다 (기본값: ~/.repo-sentinel/vault)."""
    config = load_config()
    config.vault_root = str(path.resolve())
    save_config(config)
    console.print(f"[green]vault_root 설정 완료[/green]: {config.vault_root}")


@app.command(name="set-sync-target")
def set_sync_target(path: Path = typer.Argument(..., help="NAS 등 동기화 대상 로컬 폴더")) -> None:
    """sync_target 경로를 설정한다."""
    config = load_config()
    config.sync_target = str(path.resolve())
    save_config(config)
    console.print(f"[green]sync_target 설정 완료[/green]: {config.sync_target}")


@app.command()
def tui() -> None:
    """추적 대시보드 TUI를 실행한다 (자동완성, 16색 팔레트)."""
    from repo_sentinel.tui.app import RepoSentinelApp

    RepoSentinelApp().run()


if __name__ == "__main__":
    app()
