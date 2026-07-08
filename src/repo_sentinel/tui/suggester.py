"""명령창 입력에 대한 문맥 인지 자동완성.

1번째 토큰은 명령어, 2번째 토큰은 (해당 명령이 repo_key를 받는 경우) 추적
목록, 3번째 이후 토큰은 (pick의 경우) 그 레포 안의 상대경로를 완성한다.
Textual의 Suggester에 대한 의존은 얇은 래퍼(CommandSuggester)로만 격리해서,
핵심 로직(compute_suggestion)은 Textual 없이도 단위 테스트할 수 있게 한다.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.suggester import Suggester

COMMANDS = [
    "track",
    "untrack",
    "pick",
    "relink",
    "audit",
    "sync",
    "refresh",
    "quit",
]

REPO_KEY_COMMANDS = {"pick", "p", "relink", "audit", "untrack", "ut"}


def compute_suggestion(
    value: str,
    repo_keys: list[str],
    path_candidates: Callable[[str, str], list[str]],
) -> str | None:
    if not value:
        return None
    tokens = value.split(" ")

    if len(tokens) == 1:
        prefix = tokens[0].lower()
        for cmd in COMMANDS:
            if cmd.startswith(prefix) and cmd != prefix:
                return cmd
        return None

    command = tokens[0].lower()

    if command in REPO_KEY_COMMANDS and len(tokens) == 2:
        prefix = tokens[1]
        for key in repo_keys:
            if key.lower().startswith(prefix.lower()) and key != prefix:
                return f"{tokens[0]} {key}"
        return None

    if command in {"pick", "p"} and len(tokens) >= 3:
        repo_key = tokens[1]
        prefix = tokens[-1]
        candidates = path_candidates(repo_key, prefix)
        if candidates:
            head = " ".join(tokens[:-1])
            return f"{head} {candidates[0]}"
        return None

    return None


class CommandSuggester(Suggester):
    def __init__(
        self,
        repo_keys_provider: Callable[[], list[str]],
        path_candidates_provider: Callable[[str, str], list[str]],
    ) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self._repo_keys_provider = repo_keys_provider
        self._path_candidates_provider = path_candidates_provider

    async def get_suggestion(self, value: str) -> str | None:
        return compute_suggestion(value, self._repo_keys_provider(), self._path_candidates_provider)
