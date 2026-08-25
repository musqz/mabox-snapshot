# Changelog

## 0.2.6

- Fixed `MABOX_PERSIST` never mounting at boot on real hardware:
  `_find_dev_by_path()` (used to locate the live media at boot) iterates
  `/proc/partitions` in raw kernel order and returns the first device where
  `/.miso` is found. An isohybrid image's ISO9660 content is mountable both
  from its own real MBR partition (`-partition_offset` in `isobuild.py`) and
  from the whole-disk view, and the whole disk always enumerates first --
  so it always won, and mounting it took an exclusive kernel claim on the
  entire disk that permanently blocked any other partition of the same
  device (including `MABOX_PERSIST`) from being opened read-write. Fixed by
  making `_find_dev_by_path()` scan partitions before falling back to whole
  disks. This required a new vendored `miso_boot` hook (a copy of the
  external `manjaro-tools-iso-git` package's own `miso` hook, carrying only
  this fix) for default, non-`--encrypt` builds, since mkinitcpio resolves
  `/etc/initcpio/hooks/` before this package's own
  `/usr/lib/initcpio/hooks/`, so the fix couldn't be vendored under the
  external hook's own name -- `--encrypt` builds get the same fix directly
  in the existing `miso_luks` hook. `PERSIST_HOOK_VERSION` bumped to 2 (see
  `constants.py`) since a v1-marked ISO's persistence never actually worked
  at boot.
- Fixed a second, previously-hidden bug found while real-hardware-testing
  the fix above: the ISO content's own MBR partition entry used type `0x00`,
  which `parted` (and the kernel's own msdos partition-table code) treats as
  an unused/free slot regardless of its start/size. `mabox-persistence-usb`'s
  `parted mkpart` (which auto-picks the lowest free slot when appending
  `MABOX_PERSIST`) was therefore silently reusing and overwriting that exact
  slot -- confirmed on real hardware via `blkid`, which showed the appended
  partition landing as slot 1 labeled `MABOX_PERSIST` instead of slot 3,
  with the ISO content's own partition entry gone. This has been broken
  since `mabox-persistence-usb`'s partition-appending code was first
  written; the old, always-whole-disk `_find_dev_by_path()` never depended
  on that entry existing, so nothing surfaced it until this session's fix
  made boot depend on it for the first time. Changed
  `-iso_mbr_part_type` to `0x17` ("Windows hidden IFS"), matching syslinux
  isohybrid's own long-standing default for this exact scenario: non-zero,
  so partition tools correctly see the slot as occupied, while still hidden
  from Windows auto-mount/format prompts.

## 0.2.5

- Fixed `miso_persist` resolving the wrong partition on real hardware: `_miso_persist_find_device()`
  assumed `${misodevice}` was always the whole boot disk, but `miso_luks`'s `_find_dev_by_path()` can
  resolve it to either the whole disk or one of its own partitions (an isohybrid image's ISO9660
  signature is readable both ways). When it was a partition, `/sys/block/<name>` never existed (kernel
  partitions live under `/sys/block/<parent>/<partition>`, never as their own top-level entry), so the
  scan silently landed on the wrong device -- e.g. attempting to mount the read-only `MABOX_LIVE` boot
  partition itself as `MABOX_PERSIST` and failing with `Can't open blockdev`. Now falls back to
  resolving the parent disk via the partition's `/sys/class/block` symlink.

## 0.2.4

- Added the `miso_persist` initramfs hook: every ISO now boots with support for an optional
  `MABOX_PERSIST`-labeled ext4 overlay partition on the boot device, so changes made while running
  from a USB stick can survive a reboot. A no-op when that partition isn't present -- plain and
  `--encrypt` builds boot exactly as before. The actual partition is written by the separate
  `mabox-persistence-usb` tool; this only ships the boot-time half. Every built ISO also now carries
  a `mabox/.persist-hook-version` marker so `mabox-persistence-usb` can tell whether a given ISO
  supports it. Unverified on real hardware/QEMU in this session -- see
  `docs/superpowers/specs/2026-08-20-persistent-usb-design.md`.

## 0.2.3

- Fixed `excludes add/remove/reset/edit` and `excludes rules add/remove/clear/edit` crashing with a raw
  `PermissionError` traceback when run without root -- they all write to root-owned files under
  `/etc/mabox-snapshot/`. Now they print a clean `error: ... requires root -- re-run with sudo.` and exit 1,
  matching `create`'s existing root check.
- Fixed bash tab-completion not working under `sudo mabox-snapshot ...` -- every mutating subcommand needs
  root, so that's the everyday invocation, but bash only ever dispatches completion off the first word on the
  line (`sudo`), so our completion function never ran for it. Now registered for `sudo` too, only when nothing
  else already claims that slot, so it never overrides completion for other sudo'd commands.
- Added `excludes backups {list,save,restore}`. `excludes reset` now always backs up the list it's about to
  replace first (under `~/.config/mabox-snapshot/excludes-backups/`, the invoking user's own, not root's, even
  under sudo), so it's never a one-way trip. `backups save [name]` does the same manually, and with a name
  doubles as a reusable custom template you can `backups restore` later. `backups restore <name>` rejects a
  name shaped like an absolute or `../`-relative path -- unvalidated, it would have resolved outside the
  backups directory entirely and copied arbitrary file content into the live exclude list.

## 0.2.2

- **Breaking:** `create`'s `--mode {preserving,reset}` is now a required positional argument:
  `mabox-snapshot create reset ...` instead of `mabox-snapshot create --mode reset ...`. Matches
  the rest of the CLI's subcommand style and fixes bash-completion discoverability (`create <TAB>`
  now shows `preserving reset` immediately, the same way `config <TAB>` shows its subcommands).
- Fixed bash-completion: `create`, `version`, `doctor`, `packages list`, `skel audit`, and
  `excludes rules list` now offer their flags on a bare tab press, not just after typing `-`.
- Fixed `--profile lean` leaving an unselected kernel's `mkinitcpio` preset behind while trimming
  its module tree -- Calamares regenerates every preset it finds post-install (`kernel: all`), so
  it tried and failed to rebuild an initramfs with no modules (`ERROR: module not found: 'usbhid'`),
  aborting the install. The unselected kernel's preset is now excluded too.

## 0.2.1

- Added hand-written bash tab-completion (`completions/mabox-snapshot.bash`), installed to
  `/usr/share/bash-completion/completions/mabox-snapshot`. Covers the full subcommand tree
  (including `excludes rules`) and value completion for choice flags (`--mode`, `--compression`,
  `--profile`, `--exclude-folder`, `config set`'s keys). Needs the optional `bash-completion`
  package to be active.

## 0.2.0

- `create` now writes a `.sha256` checksum file alongside the built ISO by default; disable with
  `-n`/`--no-checksums`.
- Removed unattended systemd timer automation (`mabox-snapshot.service`/`.timer`) -- no longer
  shipped or packaged.
- Added `-h` epilog examples to `config`, `config set`, `excludes`, `excludes add/remove`, and
  `excludes rules`/`rules add/remove` -- surfaces the CLI-flag-to-config-key naming convention and
  the `excludes rules` include/exclude combo without needing to drill through multiple `-h` levels.
- Added a man page (`man/mabox-snapshot.1`), installed by the package; its `@VERSION@` placeholder
  is substituted with `$pkgver` by PKGBUILD at package time, so the tracked source never needs a
  manual version bump.
- Added a test suite check that `VERSION`, `__init__.py`, `pyproject.toml`, and `PKGBUILD`'s
  `pkgver` all agree, to catch release-time version drift (pyproject.toml/__init__.py weren't
  covered by the AUR release checklist before).
- Fixed `packaging/.SRCINFO`, which was stale -- it described an unrelated `mabox-snapshot-git`
  package variant instead of matching the current `PKGBUILD`. Regenerated with `makepkg
  --printsrcinfo`.

## 0.1.0

First release.

- `create`: build a bootable live/install ISO from the running system, in two modes:
  - `preserving` -- full personal clone (real `/home`, real accounts, real passwords), optionally
    LUKS2-encrypted (`--encrypt`).
  - `reset` -- sanitized ISO for sharing, with a synthetic demo account and no real `/home` or
    saved credentials.
- Squashfs layering with selectable compression (`--compression`, `--compression-level`) and
  automatic kernel detection (`--kernel` / `--all-kernels`).
- Size/completeness tiers via `--profile`: `full` (default) or `lean`, which trims VM/container
  storage and unselected kernels' module trees.
- Exclude management: a default exclude list, locale-aware named-folder excludes
  (`--exclude-folder`), and an `excludes` subcommand (`list` / `add` / `remove` / `reset` /
  `edit` / `folders` / `rules`) for ordered include/exclude override rules.
- Change notification: compares each `create` run's home-dir scan against the previous snapshot
  and interactively offers to exclude anything new or grown past a configurable threshold
  (`--change-threshold-mb`).
- Cascading TOML configuration (`config show` / `path` / `set`): built-in defaults -> system file
  -> user file -> CLI flags.
- `packages list`: inspect explicit, AUR-reproducible, and local-only installed packages.
- `skel audit`: compare your desktop config against Mabox's shipped defaults.
- `doctor`: read-only prerequisite check (required/optional tools, free disk space, detected
  kernels).
- Unattended automation via a `mabox-snapshot.service` + `.timer` pair for periodic
  `preserving`-mode snapshots, at idle I/O priority and only on AC power.
- ISO filenames use day-month-year (European convention); snapshot history is sorted by its own
  stored timestamp, independent of the filename's display format.
