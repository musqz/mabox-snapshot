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
