from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from repo_sentinel.core import registry, scanner
from repo_sentinel.core.config import load_config

app = typer.Typer(help="PC 전역의 git 저장소를 관리하는 repo-sentinel CLI")
console = Console()


@app.command()
def scan(root: Path = typer.Argument(Path.home(), help="탐색을 시작할 루트 디렉터리")) -> None:
    """ROOT 이하에서 git 저장소를 찾아 레지스트리에 등록한다."""
    found = scanner.find_git_repos(root)
    entries = registry.merge_scanned_paths([str(p) for p in found])
    registry.save_registry(entries)
    console.print(f"[green]{len(entries)}개[/green]의 저장소를 등록했습니다.")


@app.command(name="list")
def list_repos() -> None:
    """등록된 저장소 목록을 출력한다."""
    entries = registry.load_registry()
    if not entries:
        console.print("등록된 저장소가 없습니다. 먼저 `repo-sentinel scan`을 실행하세요.")
        raise typer.Exit()

    table = Table(title="repo-sentinel registry")
    table.add_column("경로")
    table.add_column("원격 URL")
    for entry in entries:
        table.add_row(entry.path, entry.remote_url or "-")
    console.print(table)


@app.command()
def status() -> None:
    """등록된 각 저장소의 git 상태(dirty 여부)를 요약한다."""
    entries = registry.load_registry()
    if not entries:
        console.print("등록된 저장소가 없습니다. 먼저 `repo-sentinel scan`을 실행하세요.")
        raise typer.Exit()

    table = Table(title="repo status")
    table.add_column("경로")
    table.add_column("상태")
    for entry in entries:
        path = Path(entry.path)
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        state = "clean" if result.returncode == 0 and not result.stdout.strip() else "dirty"
        table.add_row(entry.path, state)
    console.print(table)


@app.command()
def sync() -> None:
    """민감 파일(dotenv 등)을 동기화 대상과 주고받는다. (미구현)"""
    load_config()
    console.print("[yellow]sync 기능은 아직 구현되지 않았습니다.[/yellow]")


if __name__ == "__main__":
    app()
