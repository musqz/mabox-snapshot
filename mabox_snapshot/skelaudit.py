"""Compares a real home directory against the vendored mabox-skel baseline
(configs/mabox-skel/skel/, installed at constants.MABOX_SKEL_DIR) --
reporting only, nothing here changes what a snapshot captures. Byte-for-
byte content identity (filecmp.cmp(shallow=False)), never mtime: skel's
own mtimes reflect package-install time, unrelated to whether you've ever
touched your copy.

Only walks skel_source's own tree, never your whole home directory --
Documents, browser profiles, Steam, etc. are out of scope for a desktop-
config audit (see mabox_snapshot.excludes/profiles for that). Feeds the
override-rule engine in excludes.py: a leaner profile can broadly exclude
a directory like .config, and this report's "differs" list tells you
exactly which specific subpaths are worth an
`excludes rules add include ...` to protect.
"""

from __future__ import annotations

import filecmp
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import constants


@dataclass(frozen=True)
class AuditEntry:
    rel_path: str
    status: str  # "identical" | "differs" | "missing" | "custom"


@dataclass
class AuditReport:
    entries: list[AuditEntry] = field(default_factory=list)

    def by_status(self, status: str) -> list[AuditEntry]:
        return [e for e in self.entries if e.status == status]


def _compare_entry(skel_path: Path, home_path: Path) -> str:
    """identical | differs -- both paths are already known to exist."""
    skel_is_link = skel_path.is_symlink()
    home_is_link = home_path.is_symlink()
    if skel_is_link or home_is_link:
        if not (skel_is_link and home_is_link):
            return "differs"  # type mismatch: one's a symlink, one isn't
        return "identical" if os.readlink(skel_path) == os.readlink(home_path) else "differs"

    if skel_path.is_dir() != home_path.is_dir():
        return "differs"  # type mismatch: file vs dir at the same relative path

    try:
        return "identical" if filecmp.cmp(skel_path, home_path, shallow=False) else "differs"
    except OSError:
        return "differs"


def _walk_skel(skel_source: Path, home: Path) -> list[AuditEntry]:
    """File-level identical/differs/missing for every file skel_source
    ships, regardless of whether its parent directory exists on the home
    side (a missing parent just means every file beneath it reports
    "missing" individually -- deliberate file-level granularity, see the
    module docstring's design note in the project plan)."""
    entries: list[AuditEntry] = []
    for dirpath, _dirnames, filenames in os.walk(skel_source):
        skel_dir = Path(dirpath)
        rel_dir = skel_dir.relative_to(skel_source)
        home_dir = home / rel_dir

        for name in filenames:
            skel_path = skel_dir / name
            home_path = home_dir / name
            rel_path = str(rel_dir / name) if str(rel_dir) != "." else name
            if home_path.exists() or home_path.is_symlink():
                entries.append(AuditEntry(rel_path, _compare_entry(skel_path, home_path)))
            else:
                entries.append(AuditEntry(rel_path, "missing"))
    return entries


def _find_custom_entries(skel_source: Path, home: Path) -> list[AuditEntry]:
    """Recurses home in lockstep with skel_source, but only ever descends
    into a home directory that skel_source also has at that exact level --
    the walk never reaches unrelated home content (Documents, .ssh, ...)
    since it can only get there through a shared parent. Extra entries are
    reported starting one level below the shared root (report_extras),
    never at the home root itself, so an entire unrelated top-level item
    (e.g. Documents) is never visited at all, let alone flagged."""
    entries: list[AuditEntry] = []

    def _recurse(skel_dir: Path, home_dir: Path, rel: Path, report_extras: bool) -> None:
        if not home_dir.is_dir() or home_dir.is_symlink():
            return
        try:
            skel_children = {c.name: c for c in skel_dir.iterdir()}
        except OSError:
            return
        try:
            home_children = {c.name: c for c in home_dir.iterdir()}
        except OSError:
            return

        if report_extras:
            for name in sorted(set(home_children) - set(skel_children)):
                child = home_children[name]
                child_rel = rel / name
                suffix = "/" if child.is_dir() and not child.is_symlink() else ""
                entries.append(AuditEntry(f"{child_rel}{suffix}", "custom"))

        for name, skel_child in skel_children.items():
            if skel_child.is_dir() and not skel_child.is_symlink() and name in home_children:
                _recurse(skel_child, home_children[name], rel / name, report_extras=True)

    _recurse(skel_source, home, Path("."), report_extras=False)
    return entries


def audit_home_against_skel(home: Path, skel_source: Path = constants.MABOX_SKEL_DIR) -> AuditReport:
    if not skel_source.exists():
        raise FileNotFoundError(
            f"vendored mabox-skel not found at {skel_source} -- is mabox-snapshot installed via its package?"
        )
    entries = _walk_skel(skel_source, home)
    entries += _find_custom_entries(skel_source, home)
    return AuditReport(entries=sorted(entries, key=lambda e: e.rel_path))


def format_report(report: AuditReport, show_identical: bool = False) -> str:
    identical = report.by_status("identical")
    differs = report.by_status("differs")
    missing = report.by_status("missing")
    custom = report.by_status("custom")

    lines: list[str] = []
    if show_identical:
        lines.append(f"identical ({len(identical)}):")
        lines.extend(f"  {e.rel_path}" for e in identical)
    else:
        lines.append(f"identical: {len(identical)} (use --show-identical to list)")

    lines.append(f"differs ({len(differs)}):")
    lines.extend(f"  {e.rel_path}" for e in differs)

    lines.append(f"missing ({len(missing)}):")
    lines.extend(f"  {e.rel_path}" for e in missing)

    lines.append(f"custom ({len(custom)}):")
    lines.extend(f"  {e.rel_path}" for e in custom)

    lines.append("")
    lines.append(
        f"{len(differs)} customized, {len(missing)} deleted since install, "
        f"{len(custom)} not from Mabox, {len(identical)} untouched"
    )
    return "\n".join(lines)
