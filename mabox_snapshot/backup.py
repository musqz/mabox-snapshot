"""Copies a finished ISO to configured backup destinations -- a local path
(e.g. an external drive mountpoint) or a user@host:path SSH target -- via
rsync, already a required dependency for this tool. Best-effort per
destination: a missing external drive or unreachable host warns and moves
on to the next one, it never fails an otherwise-successful create. This is
what makes unattended systemd-timer runs (see systemd/system/) safe to
leave running -- a temporarily unplugged backup drive shouldn't matter."""

from __future__ import annotations

import subprocess
from pathlib import Path


def build_rsync_command(src: Path, destination: str) -> list[str]:
    return ["rsync", "-a", str(src), destination]


def push_to_destinations(src: Path, destinations: tuple[str, ...]) -> list[str]:
    """Runs the rsync copy for each destination. Returns the destinations
    that failed, for the caller to warn about -- succeeded ones aren't
    returned."""
    failed = []
    for destination in destinations:
        try:
            subprocess.run(build_rsync_command(src, destination), check=True)
        except (subprocess.CalledProcessError, OSError):
            failed.append(destination)
    return failed
