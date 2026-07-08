"""추적 중인(subscribe한) 레포 목록을 관리한다.

`scan`은 읽기 전용 탐색일 뿐 아무것도 등록하지 않는다. 사용자가 명시적으로
`subscribe`한 레포만 여기 기록되며, 이때부터 vault/protect/relink/audit의
대상이 된다. 로컬 경로는 머신마다 다를 수 있으므로, 파일은 로컬(
`~/.repo-sentinel/subscriptions.json`)에 두되 다른 머신과 매칭 가능한
`repo_key`(core.repo_key 참고)를 기본 식별자로 사용한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from repo_sentinel.core.config import SUBSCRIPTIONS_FILE, ensure_config_dir


@dataclass
class Subscription:
    repo_key: str
    path: str
    remote_url: str | None = None
    is_portable: bool = True
    subscribed_at: str = ""


def load_subscriptions() -> dict[str, Subscription]:
    if not SUBSCRIPTIONS_FILE.exists():
        return {}
    data = json.loads(SUBSCRIPTIONS_FILE.read_text(encoding="utf-8"))
    return {key: Subscription(**value) for key, value in data.items()}


def save_subscriptions(subscriptions: dict[str, Subscription]) -> None:
    ensure_config_dir()
    payload = {key: asdict(sub) for key, sub in subscriptions.items()}
    SUBSCRIPTIONS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_subscription(
    repo_key: str, path: str, remote_url: str | None, is_portable: bool
) -> Subscription:
    subscriptions = load_subscriptions()
    sub = Subscription(
        repo_key=repo_key,
        path=path,
        remote_url=remote_url,
        is_portable=is_portable,
        subscribed_at=datetime.now(timezone.utc).isoformat(),
    )
    subscriptions[repo_key] = sub
    save_subscriptions(subscriptions)
    return sub


def remove_subscription(repo_key: str) -> Subscription | None:
    subscriptions = load_subscriptions()
    removed = subscriptions.pop(repo_key, None)
    if removed is not None:
        save_subscriptions(subscriptions)
    return removed
