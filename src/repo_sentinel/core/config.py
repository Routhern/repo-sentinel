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
SUBSCRIPTIONS_FILE = CONFIG_DIR / "subscriptions.json"

# vault_root: 격리된 실제 파일들이 물리적으로 보관되는 로컬 디렉터리 (기준 상태).
#   예: ~/.repo-sentinel/vault 또는 D:\data-vault
# sync_target: vault_root의 내용을 미러링하는 목적지 (예: 시놀로지 드라이브가
#   동기화하는 로컬 폴더). repo-sentinel은 이 폴더를 vault_root와 맞추기만 할 뿐,
#   다기기 동기화·버전 관리는 NAS 쪽 책임이다.
DEFAULT_VAULT_ROOT = CONFIG_DIR / "vault"

DEFAULT_SENSITIVE_PATTERNS = [".env", "*.env", "내_일기.md"]


@dataclass
class Config:
    scan_roots: list[str] = field(default_factory=list)
    vault_root: str = str(DEFAULT_VAULT_ROOT)
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
        vault_root=data.get("vault_root", str(DEFAULT_VAULT_ROOT)),
        sync_target=data.get("sync_target"),
        sensitive_patterns=data.get(
            "sensitive_patterns", list(DEFAULT_SENSITIVE_PATTERNS)
        ),
    )


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"


def save_config(config: Config) -> None:
    """설정을 config.toml에 기록한다 (스키마가 단순해 표준 라이브러리만으로 직렬화)."""
    ensure_config_dir()
    lines = [
        f"scan_roots = {_toml_array(config.scan_roots)}",
        f"vault_root = {_toml_string(config.vault_root)}",
        f"sensitive_patterns = {_toml_array(config.sensitive_patterns)}",
    ]
    if config.sync_target:
        lines.append(f"sync_target = {_toml_string(config.sync_target)}")
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
