from pathlib import Path

from repo_sentinel.core import gitignore


def test_ensure_region_creates_region_with_default_patterns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    created = gitignore.ensure_region(repo, [".env", "*.env"])

    assert created is True
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.REGION_BEGIN in text
    assert gitignore.REGION_END in text
    assert ".env" in text
    assert "*.env" in text


def test_ensure_region_appends_after_existing_content(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    gitignore.ensure_region(repo, [".env"])

    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert text.startswith("node_modules/\n")
    assert gitignore.REGION_BEGIN in text


def test_ensure_region_is_noop_when_region_already_exists(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    original = f"{gitignore.REGION_BEGIN}\ncustom.secret\n{gitignore.REGION_END}\n"
    (repo / ".gitignore").write_text(original, encoding="utf-8")

    created = gitignore.ensure_region(repo, [".env"])

    assert created is False
    assert (repo / ".gitignore").read_text(encoding="utf-8") == original


def test_read_region_patterns_extracts_non_comment_lines(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(
        f"{gitignore.REGION_BEGIN}\n# 주석\n.env\n*.env\n{gitignore.REGION_END}\n",
        encoding="utf-8",
    )

    patterns = gitignore.read_region_patterns(repo)

    assert patterns == [".env", "*.env"]


def test_read_region_patterns_returns_none_without_region(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    assert gitignore.read_region_patterns(repo) is None
    assert gitignore.read_region_patterns(tmp_path / "no-gitignore") is None


def test_resolve_patterns_prefers_region_over_fallback(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(
        f"{gitignore.REGION_BEGIN}\ncustom.secret\n{gitignore.REGION_END}\n", encoding="utf-8"
    )

    patterns = gitignore.resolve_patterns(repo, [".env"])

    assert patterns == ["custom.secret"]


def test_resolve_patterns_falls_back_without_region(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    patterns = gitignore.resolve_patterns(repo, [".env", "*.env"])

    assert patterns == [".env", "*.env"]
