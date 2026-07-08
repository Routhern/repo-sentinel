from repo_sentinel.tui.suggester import compute_suggestion


def test_suggests_command_prefix() -> None:
    assert compute_suggestion("pi", [], lambda *_: []) == "pick"


def test_no_suggestion_for_exact_or_unknown_command() -> None:
    assert compute_suggestion("pick", [], lambda *_: []) is None
    assert compute_suggestion("zzz", [], lambda *_: []) is None


def test_suggests_repo_key_for_second_token() -> None:
    # Textual의 Input은 suggestion을 "현재 값의 접두어 확장"으로 취급해 나머지를
    # 고스트 텍스트로 보여주므로, repo_key 매칭도 (부분 포함이 아니라) 접두어
    # 매칭이어야 한다. remote가 없는 로컬 전용 레포는 repo_key가 폴더명 그대로라
    # 이 방식이 자연스럽게 들어맞는다.
    repo_keys = ["apple-seed-factory", "other-repo"]

    result = compute_suggestion("pick appl", repo_keys, lambda *_: [])

    assert result == "pick apple-seed-factory"


def test_suggests_repo_key_by_host_prefix_for_portable_keys() -> None:
    repo_keys = ["github.com__me__apple-seed-factory"]

    result = compute_suggestion("pick git", repo_keys, lambda *_: [])

    assert result == "pick github.com__me__apple-seed-factory"


def test_suggests_relative_path_for_pick_third_token() -> None:
    def path_candidates(repo_key: str, prefix: str) -> list[str]:
        assert repo_key == "apple-seed-factory"
        assert prefix == "src/in"
        return ["src/input/"]

    result = compute_suggestion("pick apple-seed-factory src/in", [], path_candidates)

    assert result == "pick apple-seed-factory src/input/"


def test_no_suggestion_when_no_path_candidates() -> None:
    result = compute_suggestion("pick apple-seed-factory src/zzz", [], lambda *_: [])
    assert result is None


def test_empty_value_has_no_suggestion() -> None:
    assert compute_suggestion("", [], lambda *_: []) is None
