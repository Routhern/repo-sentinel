"""사용자별 설정과 레지스트리 파일의 위치를 정의한다.

repo-sentinel 저장소 자체는 순수 소스코드만 가지고 있어야 하므로,
스캔 결과(레지스트리)나 동기화 대상 경로 같은 사용자별 데이터는
항상 저장소 바깥, 사용자 홈 디렉터리에 저장한다.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".repo-sentinel"
CONFIG_FILE = CONFIG_DIR / "config.toml"
REGISTRY_FILE = CONFIG_DIR / "registry.json"

DEFAULT_SENSITIVE_PATTERNS = [".env", "*.env", "내_일기.md"]


@dataclass
class Config:
    scan_roots: list[str] = field(default_factory=list)
    sync_target: str | None = None
    sensitive_patterns: list[str] = field(
        default_factory=lambda: list(DEFAULT_SENSITIVE_PATTERNS)
    )


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    if not CONFIG_FILE.exists():
        return Config()
    with CONFIG_FILE.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        scan_roots=data.get("scan_roots", []),
        sync_target=data.get("sync_target"),
        sensitive_patterns=data.get(
            "sensitive_patterns", list(DEFAULT_SENSITIVE_PATTERNS)
        ),
    )
