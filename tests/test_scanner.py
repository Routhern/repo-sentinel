from pathlib import Path

from repo_sentinel.core.scanner import find_git_repos


def test_finds_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    other = tmp_path / "not_a_repo"
    other.mkdir()

    found = find_git_repos(tmp_path)

    assert found == [repo]


def test_skips_venv_and_node_modules(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / ".git").mkdir(parents=True)

    found = find_git_repos(tmp_path)

    assert found == []
