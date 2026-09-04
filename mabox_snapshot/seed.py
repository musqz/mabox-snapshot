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
import shlex
import shutil
import stat
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
    top of it at unpack time -- anything the base system's /etc/skel has
    that mabox-skel doesn't (e.g. locale-specific files) is untouched.
    mabox-skel/skel/ does now ship its own .bashrc (see that file's own
    header comment), so as of this copy .bashrc specifically comes from
    Mabox, not the base system -- it wins on a name collision like every
    other file this function seeds."""
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


def etc_skel_pseudo_specs(skel_source: Path = constants.MABOX_SKEL_DIR) -> list[str]:
    """Same vendored tree as seed_etc_skel(), but as mksquashfs -p specs
    targeting etc/skel/<relative-path> instead of a copy into an overlay
    directory -- preserving mode has no overlay step to write into (that's
    reset-mode only), so this is the only way to seed its /etc/skel too,
    using the same pseudo-file mechanism unpackfs.conf/initcpio.conf/
    services.conf already use to inject content into the squashed rootfs
    without touching the real build host's own /etc/skel. Root-owned
    (0 0), same convention as seed_etc_skel(). Walked top-down so a
    directory's own pseudo-dir entry is always emitted before any entry
    inside it -- mksquashfs's -p file specs fail outright unless their
    parent directory already exists (verified empirically, same
    requirement calamares.py's unpackfs_pseudo_specs() already documents
    for etc/calamares/). The vendored tree has no symlinks (verified: a
    plain `f`/`d` spec per entry is sufficient, no `s` spec needed).
    Each file's mode is set from its own real executable bit (same
    stat.S_IXUSR check permissions.normalize() already uses elsewhere in
    this codebase) rather than a flat 644 -- the tree genuinely ships
    executable scripts (tint2's Executor plugin runs some of these
    directly), and seed_etc_skel()'s overlay-copytree path already
    preserves them; this pseudo-file path needs the same care."""
    if not skel_source.exists():
        raise FileNotFoundError(
            f"vendored mabox-skel not found at {skel_source} -- is mabox-snapshot installed via its package?"
        )

    specs = ["etc/skel d 755 0 0"]
    for dirpath, dirnames, filenames in os.walk(skel_source):
        rel_dir = Path(dirpath).relative_to(skel_source)
        for name in sorted(dirnames):
            specs.append(f"etc/skel/{rel_dir / name} d 755 0 0")
        for name in sorted(filenames):
            source_file = Path(dirpath) / name
            mode = 755 if source_file.stat().st_mode & stat.S_IXUSR else 644
            specs.append(f"etc/skel/{rel_dir / name} f {mode} 0 0 cat {shlex.quote(str(source_file))}")
    return specs


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
