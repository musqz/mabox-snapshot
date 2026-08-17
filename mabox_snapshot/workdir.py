"""Workdir lifecycle: creation, free-space precheck, cleanup."""

from __future__ import annotations

import shutil
from pathlib import Path

from . import constants


class InsufficientSpaceError(RuntimeError):
    pass


def ensure_workdir(path: Path = constants.DEFAULT_WORKDIR) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def check_free_space(path: Path, required_bytes: int, skip: bool = False) -> None:
    """mx-snapshot's own documented guidance is ~2x the eventual ISO size
    needed during the build (squashfs + ISO coexist); the caller estimates
    required_bytes accordingly."""
    if skip:
        return
    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        free_gib = usage.free / (1024**3)
        needed_gib = required_bytes / (1024**3)
        raise InsufficientSpaceError(
            f"only {free_gib:.1f} GiB free at {path}, need ~{needed_gib:.1f} GiB "
            "(pass --skip-space-check to override)"
        )


def cleanup(path: Path, keep: bool = False) -> None:
    if keep:
        return
    if path.exists():
        shutil.rmtree(path)
