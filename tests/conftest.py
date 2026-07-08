from pathlib import Path

import pytest


def _symlinks_supported(tmp_path: Path) -> bool:
    target = tmp_path / "_symlink_probe_target"
    link = tmp_path / "_symlink_probe_link"
    target.write_text("x")
    try:
        link.symlink_to(target)
        return True
    except OSError:
        return False
    finally:
        target.unlink(missing_ok=True)
        link.unlink(missing_ok=True)


@pytest.fixture
def symlinks_supported(tmp_path: Path) -> bool:
    return _symlinks_supported(tmp_path)
