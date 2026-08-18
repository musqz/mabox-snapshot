"""Exclude-list parsing/merging, and the --exclude-folder named-directory
resolution. Patterns are plain mksquashfs -ef syntax: one path-glob per
line, relative to '/', '#' comments and blank lines ignored."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import constants, kernels


def _parse_lines(text: str) -> list[str]:
    patterns = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


class InvalidPatternError(ValueError):
    """A user-typed exclude/include pattern mksquashfs's -ef file (always
    used with -wildcards, see squashfs.py) can't accept. A leading '/',
    './', or '../' is a FATAL ERROR at actual mksquashfs build time
    ("FATAL ERROR: /, ./ and ../ prefixed excludes not supported with
    -wildcards or -regex options", verified empirically) -- but that only
    surfaces after a real build has already gone through --encrypt's
    passphrase prompt and the change-notification prompt, wasting real
    time. Catching it here, when the pattern is typed, is much cheaper.
    The single most common cause: 'sudo mabox-snapshot excludes add
    ~/foo' -- the invoking shell expands '~' using *your* $HOME before
    sudo even runs, producing an absolute path like '/home/alice/foo'."""


def _normalize_pattern(pattern: str) -> str:
    """Raises InvalidPatternError for a pattern shaped like the mistake
    above; auto-strips a bare leading '/' (the common, unambiguous case --
    there's no legitimate reason a pattern would start with one, since
    every pattern is already relative to the snapshot root) rather than
    rejecting it outright, since the fix is unambiguous. Trailing slashes
    are left alone -- verified empirically that mksquashfs handles
    'foo/' identically to 'foo' for directory excludes, unlike a leading
    slash."""
    if pattern.startswith("~"):
        raise InvalidPatternError(
            f"pattern {pattern!r} starts with '~' -- shell tilde expansion happens before sudo runs, "
            "using *your* $HOME, not root's, and mksquashfs doesn't understand '~' at all. Write out the "
            "full path relative to the snapshot root instead, e.g. 'home/alice/Downloads'."
        )
    if pattern.startswith("./") or pattern.startswith("../"):
        raise InvalidPatternError(
            f"pattern {pattern!r} starts with './' or '../' -- mksquashfs rejects these outright at build "
            "time. Write out the full path relative to the snapshot root instead, e.g. 'home/alice/Downloads'."
        )
    normalized = pattern.lstrip("/")
    if not normalized:
        raise InvalidPatternError(f"pattern {pattern!r} has no path left after stripping its leading '/'")
    return normalized


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

    def add(self, pattern: str) -> str:
        """Returns the pattern actually stored -- may differ from the
        input if _normalize_pattern() stripped a leading '/'; the caller
        (cli.py) uses this to tell the user when that happened."""
        pattern = _normalize_pattern(pattern)
        patterns = self.load()
        if pattern not in patterns:
            patterns.append(pattern)
            self._save(patterns)
        return pattern

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
    override_rules_path: Path = constants.OVERRIDE_RULES_FILE,
    override_root: Path = Path("/"),
) -> list[str]:
    """The full merged, deduplicated pattern list for one snapshot run."""
    patterns = list(ExcludeList(exclude_list_path).load())
    patterns += detect_swap_paths(fstab)
    patterns += resolve_folder_excludes(extra_folders, home)
    if mode == "reset":
        patterns += constants.RESET_MODE_ONLY_EXCLUDES
    patterns += compile_override_rules(OverrideRuleList(override_rules_path).load(), root=override_root)

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


def exclude_unselected_kernel_modules(
    all_kernels: list[kernels.KernelInfo],
    selected_kernels: list[kernels.KernelInfo],
    module_versions: dict[str, str],
) -> list[str]:
    """usr/lib/modules/<version>/* for every installed kernel not selected
    for this build -- 200-600MB per kernel that otherwise always rides
    along in the rootfs squashfs regardless of --kernel/--all-kernels,
    since only which vmlinuz/initramfs get copied to iso_root/boot is
    controlled today, never which kernel module trees get excluded from
    the live-'/' scan. Dynamic (depends on this run's kernel selection),
    so unlike the rest of this module it can't be a static excludes.list
    pattern -- see profiles.py's trim_unselected_kernel_modules."""
    selected_names = {k.name for k in selected_kernels}
    patterns = []
    for kernel in all_kernels:
        if kernel.name in selected_names:
            continue
        version = module_versions.get(kernel.name)
        if version is None:
            continue  # defensively skip rather than KeyError -- module_version() can fail
        patterns.append(f"usr/lib/modules/{version}/*")
    return patterns


# ---------------------------------------------------------------------------
# Ordered include/exclude override rules
#
# excludes.list above stays a flat, unordered, pure-exclude list -- it
# already works and there's no need to retrofit a breaking format change
# onto ~40 shipped default patterns. This is a separate, additive,
# power-user file for the case that list structurally can't express:
# "exclude this broad directory, but keep one specific subpath inside it".
# mksquashfs's -ef exclude file has no include/negation semantics at all,
# so these ordered rules are compiled down into a flat, mksquashfs-
# compatible pattern set by compile_override_rules() before ever reaching
# mksquashfs -- it never sees an "include" concept, only the expanded
# result.
# ---------------------------------------------------------------------------

_RULE_ACTIONS = ("exclude", "include")

# Characters mksquashfs's -wildcards mode treats as glob metacharacters --
# same set _escape_glob() above already guards against for foreign-mount
# labels; reused here since compile_override_rules() also turns real,
# walked directory-entry names into concrete exclude patterns.
_RULE_GLOB_METACHARS = _GLOB_METACHARS


@dataclass(frozen=True)
class OverrideRule:
    action: str  # "exclude" | "include"
    pattern: str  # relative to '/', mksquashfs-style glob allowed on the exclude side only


class UnsupportedRuleNestingError(ValueError):
    """An exclude rule falls under an already-protected include -- a second
    level of exclude/include alternation, unsupported in v1: it would mean
    silently deciding whose intent wins rather than compiling unambiguously."""


def _parse_rule_lines(text: str) -> list[OverrideRule]:
    rules = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or parts[0] not in _RULE_ACTIONS:
            raise ValueError(f"line {lineno}: expected 'exclude <path>' or 'include <path>', got: {raw_line!r}")
        action, pattern = parts
        rules.append(OverrideRule(action=action, pattern=pattern.strip()))
    return rules


def _format_rule_lines(rules: list[OverrideRule]) -> str:
    return "\n".join(f"{r.action} {r.pattern}" for r in rules)


class OverrideRuleList:
    """Wraps the persisted, user-editable override-rule file. Same shape as
    ExcludeList, no shipped default to reset to -- empty/absent by default."""

    def __init__(self, path: Path = constants.OVERRIDE_RULES_FILE):
        self.path = path

    def load(self) -> list[OverrideRule]:
        if not self.path.exists():
            return []
        return _parse_rule_lines(self.path.read_text())

    def _save(self, rules: list[OverrideRule]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(_format_rule_lines(rules) + "\n" if rules else "")

    def add(self, action: str, pattern: str) -> str:
        """Returns the pattern actually stored -- see ExcludeList.add()."""
        if action not in _RULE_ACTIONS:
            raise ValueError(f"action must be 'exclude' or 'include', got: {action!r}")
        pattern = _normalize_pattern(pattern)
        rules = self.load()
        rule = OverrideRule(action=action, pattern=pattern)
        if rule not in rules:
            rules.append(rule)
            self._save(rules)
        return pattern

    def remove(self, action: str, pattern: str) -> None:
        self._save([r for r in self.load() if not (r.action == action and r.pattern == pattern)])

    def clear(self) -> None:
        self._save([])

    def edit(self) -> int:
        if not self.path.exists():
            self._save([])
        editor = os.environ.get("EDITOR", "nano")
        return subprocess.call([editor, str(self.path)])


def _walk_and_protect(base: Path, keep_tree: dict, root: Path) -> list[str]:
    """Bounded ancestor-chain walk: only ever visits directories on the
    path to a protected leaf, one iterdir() per level. keep_tree maps a
    child name to its own subtree dict -- an empty subtree means that
    child is the protected leaf itself (kept, never recursed into further);
    a non-empty subtree means there are deeper protected paths below it."""
    if not base.is_dir():
        return []
    try:
        entries = list(base.iterdir())
    except OSError:
        return []

    result: list[str] = []
    for entry in entries:
        subtree = keep_tree.get(entry.name)
        if subtree is not None:
            if subtree:
                result.extend(_walk_and_protect(entry, subtree, root))
            continue  # protected leaf (subtree == {}) or an interior node -- never excluded itself

        try:
            rel = entry.relative_to(root)
        except ValueError:
            continue
        rel_text = _escape_glob(str(rel))
        if "\n" in rel_text:
            continue  # can't be represented as one line in a newline-delimited -ef file
        result.append(rel_text)
    return result


def _pair_includes(rules: list[OverrideRule]) -> tuple[dict[OverrideRule, list[OverrideRule]], list[OverrideRule]]:
    """Pairs each include with its nearest enclosing exclude (longest
    matching ancestor pattern earlier in the effective rule set). Returns
    (exclude -> paired includes, orphan includes with no enclosing
    exclude at all)."""
    exclude_rules = [r for r in rules if r.action == "exclude"]
    include_rules = [r for r in rules if r.action == "include"]

    groups: dict[OverrideRule, list[OverrideRule]] = {}
    orphans: list[OverrideRule] = []
    for include in include_rules:
        candidates = [ex for ex in exclude_rules if include.pattern.startswith(ex.pattern + "/")]
        if not candidates:
            orphans.append(include)
            continue
        nearest = max(candidates, key=lambda ex: len(ex.pattern))
        groups.setdefault(nearest, []).append(include)
    return groups, orphans


def find_orphan_includes(rules: list[OverrideRule]) -> list[OverrideRule]:
    """Include rules with no enclosing exclude anywhere in the rule set --
    a no-op, not an error, but worth surfacing to the user (see cli.py's
    `excludes rules list`)."""
    _, orphans = _pair_includes(rules)
    return orphans


def compile_override_rules(rules: list[OverrideRule], root: Path = Path("/")) -> list[str]:
    """Expands ordered exclude/include rules into flat mksquashfs -ef
    patterns. Each include pairs with its nearest enclosing exclude
    (longest matching ancestor pattern); a bare include with no enclosing
    exclude is a no-op (see find_orphan_includes() for surfacing that to
    a user). An exclude with no paired include passes straight through
    with no filesystem access, same cost as today. A paired
    exclude+include is expanded via a bounded directory walk (see
    _walk_and_protect) that visits only the ancestor chain down to the
    protected leaf(ves), never the whole subtree. Raises
    UnsupportedRuleNestingError if an exclude rule falls under an
    already-protected include, or ValueError if an include's protected
    suffix (the part past its enclosing exclude) contains a glob."""
    exclude_rules = [r for r in rules if r.action == "exclude"]
    groups, _orphans = _pair_includes(rules)

    protected = [inc for incs in groups.values() for inc in incs]
    for include in protected:
        for exclude in exclude_rules:
            if exclude.pattern.startswith(include.pattern + "/"):
                raise UnsupportedRuleNestingError(
                    f"'exclude {exclude.pattern}' falls under already-protected 'include {include.pattern}' -- "
                    "a second level of exclude/include alternation isn't supported"
                )

    compiled: list[str] = []
    for exclude in exclude_rules:
        includes = groups.get(exclude)
        if not includes:
            compiled.append(exclude.pattern)
            compiled.append(f"{exclude.pattern}/*")
            continue

        keep_tree: dict = {}
        for include in includes:
            suffix = include.pattern[len(exclude.pattern) + 1 :]
            if not suffix or any(c in _RULE_GLOB_METACHARS for c in suffix):
                raise ValueError(
                    f"include '{include.pattern}' under exclude '{exclude.pattern}': protected suffix "
                    "must be a non-empty literal path -- wildcards aren't supported there"
                )
            node = keep_tree
            components = suffix.split("/")
            for component in components[:-1]:
                node = node.setdefault(component, {})
            node.setdefault(components[-1], {})

        for base in sorted(root.glob(exclude.pattern)):
            compiled.extend(_walk_and_protect(base, keep_tree, root))

    seen: set[str] = set()
    result = []
    for pattern in compiled:
        if pattern not in seen:
            seen.add(pattern)
            result.append(pattern)
    return result
