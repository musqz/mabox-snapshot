"""Compares the current home-dir scan against the most recent stored
manifest (see history.py) and, for anything new or grown past a size
threshold, interactively offers to keep it in this snapshot or exclude it.
Exclusions are for this run only -- never touches the persisted
excludes.list (use `mabox-snapshot excludes add` for a permanent one)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .history import HistoryEntry


@dataclass
class ChangedEntry:
    name: str
    type: str
    size_bytes: int
    delta_bytes: int  # size_bytes for new entries, growth for existing ones
    is_new: bool


def diff_entries(
    previous: list[HistoryEntry], current: list[HistoryEntry], threshold_bytes: int
) -> list[ChangedEntry]:
    """Entries that are new, or have grown, by at least threshold_bytes since
    the previous manifest. Shrunk or unchanged entries are never flagged."""
    previous_by_name = {e.name: e for e in previous}
    changed = []
    for entry in current:
        prev = previous_by_name.get(entry.name)
        delta = entry.size_bytes if prev is None else entry.size_bytes - prev.size_bytes
        if delta >= threshold_bytes:
            changed.append(
                ChangedEntry(
                    name=entry.name, type=entry.type, size_bytes=entry.size_bytes,
                    delta_bytes=delta, is_new=prev is None,
                )
            )
    return changed


def _exclude_pattern(home: Path, entry: ChangedEntry) -> str:
    rel = (home / entry.name).relative_to("/")
    return f"{rel}/*" if entry.type == "dir" else str(rel)


def prompt_for_exclusions(changed: list[ChangedEntry], home: Path) -> list[str]:
    """Interactively asks, one at a time, whether to exclude each changed
    entry from this run's snapshot. Non-interactive stdin (no tty -- e.g. a
    scheduled/headless run) skips prompting entirely and keeps everything,
    since silently excluding data a human never approved would be the more
    dangerous default."""
    if not changed:
        return []

    if not sys.stdin.isatty():
        names = ", ".join(c.name for c in changed)
        print(
            f"note: {len(changed)} new/grown item(s) in home since last snapshot "
            f"({names}) -- kept (non-interactive)"
        )
        return []

    excluded = []
    for c in changed:
        verb = "new" if c.is_new else "grown"
        mb = c.delta_bytes / (1024**2)
        total_mb = c.size_bytes / (1024**2)
        print(f"{c.name} is {verb}: +{mb:.0f} MiB (now {total_mb:.0f} MiB)")
        answer = input("  keep in this snapshot? [K/e] ").strip().lower()
        if answer == "e":
            excluded.append(_exclude_pattern(home, c))
    return excluded
