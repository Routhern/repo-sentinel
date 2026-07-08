"""dotenv, 개인 파일(예: 내_일기.md), 중간 산출물을 동기화 대상(예: 시놀로지 NAS)과 주고받는다.

동기화 프로토콜(rsync/smb 마운트 경로 등)은 아직 확정되지 않았다.
현재는 민감 파일을 찾아내는 부분만 구현하고, 실제 전송은 스텁으로 남겨둔다.
"""

from __future__ import annotations

from pathlib import Path

from repo_sentinel.core.config import Config


def find_sensitive_files(repo_path: Path, config: Config) -> list[Path]:
    matches: list[Path] = []
    for pattern in config.sensitive_patterns:
        matches.extend(repo_path.rglob(pattern))
    return matches


def push_to_sync_target(repo_path: Path, config: Config) -> None:
    if not config.sync_target:
        raise RuntimeError("sync_target이 설정되지 않았습니다 (~/.repo-sentinel/config.toml)")
    raise NotImplementedError("동기화 대상으로의 전송 로직은 아직 구현되지 않았습니다")


def pull_from_sync_target(repo_path: Path, config: Config) -> None:
    if not config.sync_target:
        raise RuntimeError("sync_target이 설정되지 않았습니다 (~/.repo-sentinel/config.toml)")
    raise NotImplementedError("동기화 대상으로부터의 수신 로직은 아직 구현되지 않았습니다")
