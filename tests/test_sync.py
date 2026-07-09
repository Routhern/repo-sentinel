import os
import time
from pathlib import Path

import pytest

from repo_sentinel.core.sync import pull_from_sync_target, push_to_sync_target


def test_push_copies_new_files(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    sync_target = tmp_path / "nas"
    (vault_root / "repo-a.repo-sentinel-vault").mkdir(parents=True)
    (vault_root / "repo-a.repo-sentinel-vault" / "data.csv").write_text("v1", encoding="utf-8")

    copied = push_to_sync_target(vault_root, sync_target)

    assert copied == ["repo-a.repo-sentinel-vault/data.csv"]
    assert (sync_target / "repo-a.repo-sentinel-vault" / "data.csv").read_text(encoding="utf-8") == "v1"


def test_pull_copies_newer_files_only(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    sync_target = tmp_path / "nas"
    vault_root.mkdir()
    sync_target.mkdir()

    old_file = vault_root / "data.csv"
    old_file.write_text("old", encoding="utf-8")

    time.sleep(0.05)
    new_file = sync_target / "data.csv"
    new_file.write_text("new", encoding="utf-8")
    newer_time = time.time() + 10
    os.utime(new_file, (newer_time, newer_time))

    copied = pull_from_sync_target(vault_root, sync_target)

    assert copied == ["data.csv"]
    assert (vault_root / "data.csv").read_text(encoding="utf-8") == "new"


def test_push_skips_when_destination_is_newer(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    sync_target = tmp_path / "nas"
    vault_root.mkdir()
    sync_target.mkdir()

    (vault_root / "data.csv").write_text("stale", encoding="utf-8")
    dest = sync_target / "data.csv"
    dest.write_text("fresh", encoding="utf-8")
    newer_time = time.time() + 10
    os.utime(dest, (newer_time, newer_time))

    copied = push_to_sync_target(vault_root, sync_target)

    assert copied == []
    assert dest.read_text(encoding="utf-8") == "fresh"


def test_pull_skips_symlinked_file(tmp_path: Path, symlinks_supported: bool) -> None:
    """sync_target 안의 파일 심볼릭 링크가 그 대상 내용을 vault로 끌어오지 못해야 한다."""
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    vault_root = tmp_path / "vault"
    sync_target = tmp_path / "nas"
    vault_root.mkdir()
    sync_target.mkdir()

    secret = tmp_path / "secret.txt"
    secret.write_text("id_rsa contents", encoding="utf-8")
    (sync_target / "exfil.txt").symlink_to(secret)

    copied = pull_from_sync_target(vault_root, sync_target)

    assert copied == []
    assert not (vault_root / "exfil.txt").exists()


def test_pull_skips_symlinked_directory(tmp_path: Path, symlinks_supported: bool) -> None:
    """sync_target 안의 디렉터리 심볼릭 링크 아래로 내려가 파일을 복사하지 않아야 한다."""
    if not symlinks_supported:
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 권한이 없습니다 (Windows 개발자 모드 필요)")

    vault_root = tmp_path / "vault"
    sync_target = tmp_path / "nas"
    vault_root.mkdir()
    sync_target.mkdir()

    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    (secret_dir / "id_rsa").write_text("private key", encoding="utf-8")
    (sync_target / "exfil").symlink_to(secret_dir, target_is_directory=True)

    copied = pull_from_sync_target(vault_root, sync_target)

    assert copied == []
    assert not (vault_root / "exfil").exists()
