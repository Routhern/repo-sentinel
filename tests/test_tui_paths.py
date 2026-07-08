from pathlib import Path

from repo_sentinel.tui.paths import relative_path_candidates


def test_completes_top_level_entries(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("x")

    candidates = relative_path_candidates(tmp_path, "")

    assert "src/" in candidates
    assert "README.md" in candidates


def test_completes_within_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "src" / "input").mkdir(parents=True)
    (tmp_path / "src" / "input" / "data.csv").write_text("x")
    (tmp_path / "src" / "other.py").write_text("x")

    candidates = relative_path_candidates(tmp_path, "src/in")

    assert candidates == ["src/input/"]


def test_hides_dotfiles_unless_prefix_starts_with_dot(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("secret")
    (tmp_path / "app.py").write_text("x")

    assert relative_path_candidates(tmp_path, "") == ["app.py"]
    assert relative_path_candidates(tmp_path, ".") == [".env"]


def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert relative_path_candidates(tmp_path, "nope/deep") == []
