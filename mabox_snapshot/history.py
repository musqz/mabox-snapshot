"""Per-run snapshot manifest: after each successful `create`, records a
lightweight TOML snapshot of the invoking user's top-level home-dir entries
(name/type/size) so a later run can compare "what's new since last time."
Purely comparison metadata -- never touches actual home-dir contents, and
has no revert/backup capability. Hand-written TOML writer, not a library
(same rationale as config.py's set_value -- see config.py:74-75): stdlib
tomllib is read-only, and the format here is a flat header plus one
repeated [[entries]] table, trivial to emit as text."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import constants, privilege


@dataclass
class HistoryEntry:
    name: str
    type: str  # "file" or "dir"
    size_bytes: int


@dataclass
class HistoryRecord:
    timestamp: str
    mode: str
    iso: str
    entries: list[HistoryEntry] = field(default_factory=list)


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def scan_home_entries(home: Path) -> list[HistoryEntry]:
    """Top-level children of home only -- not a recursive listing. Directories
    get the recursive total of file sizes beneath them; files get their own
    size. Runs the same way regardless of --mode: this tracks the live
    filesystem's home-dir growth, independent of what a given ISO contains."""
    if not home.exists():
        raise FileNotFoundError(f"home directory {home} does not exist")

    entries = []
    for child in sorted(home.iterdir()):
        if child.is_dir():
            entries.append(HistoryEntry(name=child.name, type="dir", size_bytes=_dir_size(child)))
        elif child.is_file():
            entries.append(HistoryEntry(name=child.name, type="file", size_bytes=child.stat().st_size))
    return entries


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_manifest(record: HistoryRecord) -> str:
    lines = [
        f'timestamp = "{_toml_escape(record.timestamp)}"',
        f'mode = "{_toml_escape(record.mode)}"',
        f'iso = "{_toml_escape(record.iso)}"',
    ]
    for entry in record.entries:
        lines += [
            "",
            "[[entries]]",
            f'name = "{_toml_escape(entry.name)}"',
            f'type = "{entry.type}"',
            f"size_bytes = {entry.size_bytes}",
        ]
    return "\n".join(lines) + "\n"


def write_manifest(
    dest: Path,
    mode: str,
    history_dir: Path = constants.HISTORY_DIR,
    home: Path | None = None,
    entries: list[HistoryEntry] | None = None,
    timestamp: str | None = None,
) -> Path:
    """Writes history_dir/{dest.stem}.toml recording the top-level home-dir
    entries at the time of a successful `create` run. Reusing the ISO's own
    filename stem (rather than a bare timestamp) means the manifest inherits
    whatever mode-qualified naming/collision semantics the ISO filename
    itself already has. `home` defaults to
    privilege.resolve_home_dir(); tests pass it explicitly to bypass
    SUDO_USER entirely. `entries` lets a caller that already scanned home
    (e.g. cli.py's change-notification pass) pass that scan straight through
    instead of paying for a second walk of the same tree. `timestamp`
    defaults to datetime.now(); tests pass it explicitly for deterministic,
    collision-free ordering in list_history()/latest()."""
    if entries is None:
        if home is None:
            home = privilege.resolve_home_dir()
        entries = scan_home_entries(home)

    record = HistoryRecord(
        timestamp=timestamp or datetime.now().isoformat(timespec="seconds"),
        mode=mode,
        iso=dest.name,
        entries=entries,
    )

    history_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = history_dir / f"{dest.stem}.toml"
    manifest_path.write_text(render_manifest(record))
    return manifest_path


def _parse_record(path: Path) -> HistoryRecord:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    entries = [
        HistoryEntry(name=e["name"], type=e["type"], size_bytes=e["size_bytes"])
        for e in raw.get("entries", [])
    ]
    return HistoryRecord(timestamp=raw["timestamp"], mode=raw["mode"], iso=raw["iso"], entries=entries)


def list_history(history_dir: Path = constants.HISTORY_DIR) -> list[HistoryRecord]:
    """All stored manifests, oldest first. Sorted by each record's own
    stored `timestamp` field, not by manifest filename -- the filename
    derives from the ISO's own display-oriented stamp (day-month-year,
    European convention; see cli.py), which is deliberately NOT
    lexicographically sortable, unlike the ISO 8601 `timestamp` field
    written by write_manifest()."""
    if not history_dir.exists():
        return []
    records = [_parse_record(p) for p in history_dir.glob("*.toml")]
    return sorted(records, key=lambda r: datetime.fromisoformat(r.timestamp))


def latest(n: int = 2, history_dir: Path = constants.HISTORY_DIR) -> list[HistoryRecord]:
    """The n most recent manifests, oldest-of-the-selected-window first."""
    if n <= 0:
        return []
    return list_history(history_dir)[-n:]
