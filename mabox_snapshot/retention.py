"""Deletes old snapshot ISOs by age. output_dir accumulates one .iso per
`create` run; this prunes anything past a configured retention window. Only
ever touches this tool's own mabox-*.iso naming, never arbitrary files a
user might have parked in the same output directory."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from . import constants


def prune_old_isos(output_dir: Path, max_age_days: int, now: datetime | None = None) -> list[Path]:
    """Deletes output_dir/mabox-*.iso files older than max_age_days. A single
    file's removal failing (permissions, race) is logged and skipped rather
    than aborting the rest of the batch, matching this codebase's per-item
    resilience convention (see permissions.py, seed.py)."""
    if not output_dir.exists():
        return []
    if now is None:
        now = datetime.now()

    deleted = []
    for iso in sorted(output_dir.glob(f"{constants.ISO_NAME_PREFIX}*.iso")):
        age_days = (now - datetime.fromtimestamp(iso.stat().st_mtime)).days
        if age_days > max_age_days:
            try:
                iso.unlink()
                deleted.append(iso)
            except OSError as e:
                print(f"warning: could not remove old snapshot {iso}: {e}", file=sys.stderr)
    return deleted
