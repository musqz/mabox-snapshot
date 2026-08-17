"""Demo-account desktop seeding for reset mode: copies the vendored
Mabox/mabox-skel skel/ tree (see configs/mabox-skel/, SOURCES.md) into the
overlay's home/demo/, then chowns it to demo's uid/gid. Never reads or
writes the live filesystem's own /home.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from . import constants

logger = logging.getLogger(__name__)


def seed_demo_home(overlay_dir: Path, skel_source: Path = constants.MABOX_SKEL_DIR) -> Path:
    if not skel_source.exists():
        raise FileNotFoundError(
            f"vendored mabox-skel not found at {skel_source} -- is mabox-snapshot installed via its package?"
        )

    dest = overlay_dir / "home" / constants.DEMO_USERNAME
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skel_source, dest, symlinks=True)

    chown_recursive(dest, constants.DEMO_UID, constants.DEMO_GID)
    return dest


def chown_recursive(root: Path, uid: int, gid: int) -> None:
    _chown(root, uid, gid)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        for name in dirnames + filenames:
            _chown(current / name, uid, gid)


def _chown(path: Path, uid: int, gid: int) -> None:
    try:
        os.chown(path, uid, gid, follow_symlinks=False)
    except OSError as e:
        logger.warning("seed: chown %s: %s", path, e)
