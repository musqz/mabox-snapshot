"""Umask-safety permission normalization.

Walks a tree the tool itself created (never the live filesystem) and
forces explicit modes, since os.makedirs/open(...,'w')/shutil.copytree
are all shaped by the calling process's umask. Logs and continues on any
single chmod failure rather than aborting the whole pass -- the direct
lesson from a real bug found this session in a sibling Go project, where
a permission-normalization walk aborted entirely on its first error.
"""

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

DIR_MODE = 0o755
EXEC_FILE_MODE = 0o755
FILE_MODE = 0o644


def normalize(root: Path) -> None:
    for dirpath, _dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        _chmod(current, DIR_MODE)
        for name in filenames:
            path = current / name
            if path.is_symlink():
                continue
            try:
                is_exec = bool(path.stat().st_mode & stat.S_IXUSR)
            except OSError as e:
                logger.warning("normalize: stat %s: %s", path, e)
                continue
            _chmod(path, EXEC_FILE_MODE if is_exec else FILE_MODE)


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError as e:
        logger.warning("normalize: chmod %s: %s", path, e)
