"""Desktop seeding for reset mode: copies the vendored Mabox/mabox-skel
skel/ tree (see configs/mabox-skel/, SOURCES.md) to two places -- the
overlay's home/demo/ (for the live "try before you install" session,
chowned to demo's uid/gid) and etc/skel/ (root-owned, so any account
created afterward -- Calamares' own users job during a real install, or
a plain useradd -- gets the same desktop instead of the live rootfs's
own bare /etc/skel; confirmed against a real install: without this, a
freshly-created account landed with just a generic Openbox right-click
menu, none of Mabox's own tint2/jgmenu/openbox config). Never reads or
writes the live filesystem's own /home or /etc/skel.
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


def seed_etc_skel(overlay_dir: Path, skel_source: Path = constants.MABOX_SKEL_DIR) -> Path:
    """Same vendored tree as seed_demo_home(), copied to etc/skel/
    instead -- root-owned (standard skel convention; each account's own
    creation step does its own chown on copy, same as it already does
    for whatever the rootfs layer's stock /etc/skel contains). The
    rootfs layer's own /etc/skel is never excluded (see constants.py's
    RESET_MODE_ONLY_EXCLUDES), so this only adds Mabox's own dotfiles on
    top of it at unpack time -- unrelated skel content (.bashrc, etc.)
    from the base system is untouched."""
    if not skel_source.exists():
        raise FileNotFoundError(
            f"vendored mabox-skel not found at {skel_source} -- is mabox-snapshot installed via its package?"
        )

    dest = overlay_dir / "etc" / "skel"
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skel_source, dest, symlinks=True)

    chown_recursive(dest, 0, 0)
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
