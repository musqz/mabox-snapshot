"""Exclude-list parsing/merging, and the --exclude-folder named-directory
resolution. Patterns are plain mksquashfs -ef syntax: one path-glob per
line, relative to '/', '#' comments and blank lines ignored."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import constants


def _parse_lines(text: str) -> list[str]:
    patterns = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


class ExcludeList:
    """Wraps the persisted, user-editable exclude-list file."""

    def __init__(self, path: Path = constants.EXCLUDES_LIST_FILE):
        self.path = path

    def load(self) -> list[str]:
        if not self.path.exists():
            return []
        return _parse_lines(self.path.read_text())

    def _save(self, patterns: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(patterns) + "\n" if patterns else "")

    def add(self, pattern: str) -> None:
        patterns = self.load()
        if pattern not in patterns:
            patterns.append(pattern)
            self._save(patterns)

    def remove(self, pattern: str) -> None:
        self._save([p for p in self.load() if p != pattern])

    def reset(self, default_source: Path = constants.EXCLUDES_LIST_DEFAULT) -> None:
        if not default_source.exists():
            raise FileNotFoundError(
                f"shipped default not found at {default_source} -- is mabox-snapshot installed via its package?"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(default_source, self.path)

    def edit(self) -> int:
        if not self.path.exists():
            self._save([])
        editor = os.environ.get("EDITOR", "nano")
        return subprocess.call([editor, str(self.path)])


def resolve_user_dirs(home: Path | None = None) -> dict[str, Path]:
    """Parse ~/.config/user-dirs.dirs. Respects localized/renamed folder
    names (Mabox ships en/es/pl) -- never assume English directory names."""
    home = home or Path.home()
    dirs_file = home / ".config" / "user-dirs.dirs"
    result: dict[str, Path] = {}
    if not dirs_file.exists():
        return result

    for line in dirs_file.read_text().splitlines():
        line = line.strip()
        if not line.startswith("XDG_") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key.endswith("_DIR"):
            continue
        name = key[len("XDG_"):-len("_DIR")].title()
        value = value.strip().strip('"').replace("$HOME", str(home))
        result[name] = Path(value)
    return result


def resolve_folder_excludes(names: tuple[str, ...], home: Path | None = None) -> list[str]:
    home = home or Path.home()
    user_dirs = resolve_user_dirs(home)
    excludes = []
    for name in names:
        path = user_dirs.get(name)
        if path is None:
            continue  # not defined for this user -- nothing to exclude
        try:
            rel = path.relative_to("/")
        except ValueError:
            continue
        excludes.append(f"{rel}/*")
    return excludes


def detect_swap_paths(fstab: Path = constants.FSTAB_FILE) -> list[str]:
    """File-based swap entries from /etc/fstab, as relative excludes.
    UUID=/LABEL=/PARTUUID= entries reference whole partitions, not files
    under the captured tree, and are skipped."""
    if not fstab.exists():
        return []

    excludes = []
    for line in fstab.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 3:
            continue
        device, _mountpoint, fstype = fields[0], fields[1], fields[2]
        if fstype == "swap" and device.startswith("/"):
            excludes.append(device.lstrip("/"))
    return excludes


# /proc/mounts escapes space, tab, newline, and backslash in path fields
# (kernel's mangle_path()) -- backslash last, so unescaping it can't create
# a spurious match for one of the other three sequences.
_MOUNTS_ESCAPES = [("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")]


def _unescape_mounts_field(raw: str) -> str:
    for escaped, char in _MOUNTS_ESCAPES:
        raw = raw.replace(escaped, char)
    return raw


# Characters mksquashfs's -wildcards mode (fnmatch-style globbing) treats as
# special. A mount label containing one of these (e.g. a drive named
# "Backup [2024]") would otherwise be silently misparsed as a glob and never
# match the real path -- defeating the exclude entirely.
_GLOB_METACHARS = frozenset("\\[]*?")


def _escape_glob(text: str) -> str:
    return "".join(f"\\{c}" if c in _GLOB_METACHARS else c for c in text)


def detect_foreign_mount_excludes(
    root: Path = Path("/"),
    allowed: tuple[Path, ...] = constants.ALLOWED_ROOTFS_MOUNTS,
    mounts: Path = constants.MOUNTS_FILE,
) -> list[str]:
    """Any filesystem mounted under root other than root itself is either a
    real system partition worth capturing (allowed: /boot, /home, and
    anything mounted under them e.g. a separate /boot/efi) or incidental/
    removable storage -- a backup drive, a USB stick, a custom data volume
    like /mount/<name> -- that has nothing to do with the OS and can
    silently balloon a snapshot to hundreds of GB if crossed into. The
    latter are excluded wholesale, by mountpoint rather than a fixed path
    list, so any such volume is caught regardless of where it's mounted.

    Classified by device id (stat().st_dev), not just mountpoint presence
    in /proc/mounts -- the same check mksquashfs's own -one-file-system
    uses. This matters for Btrfs subvolume layouts (@, @home, @var, ...),
    a common Arch/Manjaro setup: each subvolume gets its own /proc/mounts
    entry with its own mountpoint but shares the root filesystem's device,
    so it's correctly treated as part of the same filesystem, not foreign
    storage, with no need to allowlist every subvolume by name."""
    if not mounts.exists():
        return []

    root = root.resolve()
    allowed = tuple(a.resolve() for a in allowed)
    try:
        root_dev = os.stat(root).st_dev
    except OSError:
        return []

    excludes = []
    seen: set[str] = set()
    for line in mounts.read_text(errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        mountpoint = Path(_unescape_mounts_field(fields[1]))
        if mountpoint == root:
            continue
        if any(mountpoint.is_relative_to(a) for a in allowed):
            continue
        try:
            rel = mountpoint.relative_to(root)
        except ValueError:
            continue  # not under root at all
        try:
            if os.stat(mountpoint).st_dev == root_dev:
                continue  # same filesystem (e.g. a Btrfs subvolume), not foreign storage
        except OSError:
            pass  # can't verify -- fall through and exclude it to be safe
        rel_text = _escape_glob(str(rel))
        if "\n" in rel_text:
            continue  # can't be represented as one line in a newline-delimited -ef file
        pattern = f"{rel_text}/*"
        if pattern not in seen:
            seen.add(pattern)
            excludes.append(pattern)
    return excludes


def resolve_excludes(
    mode: str,
    exclude_list_path: Path = constants.EXCLUDES_LIST_FILE,
    extra_folders: tuple[str, ...] = (),
    home: Path | None = None,
    fstab: Path = constants.FSTAB_FILE,
) -> list[str]:
    """The full merged, deduplicated pattern list for one snapshot run."""
    patterns = list(ExcludeList(exclude_list_path).load())
    patterns += detect_swap_paths(fstab)
    patterns += resolve_folder_excludes(extra_folders, home)
    if mode == "reset":
        patterns += constants.RESET_MODE_ONLY_EXCLUDES

    seen: set[str] = set()
    result = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def write_mksquashfs_exclude_file(patterns: list[str], dest: Path) -> Path:
    dest.write_text("\n".join(patterns) + "\n" if patterns else "")
    return dest
