# Changelog

## 0.3.2

- Fixed a real pcmanfm crash on navigating into `/usr/share/backgrounds`:
  vendored mabox-skel shipped an invalid `ViewMode=thumbnails` (plural) for
  that folder's per-directory libfm setting, unlike the correct singular
  value already used for `~/wallpapers`. Corrected to `ViewMode=thumbnail`.
- mabox-skel now ships a default `.bashrc`. It never had one before, so
  reset mode's `demo` account (and any account seeded from `etc/skel` on a
  fresh preserving-mode build) got no shell aliases at all -- not even
  bash's own stock defaults, let alone Mabox's own (`theme.sh` integration,
  `mabox-todo.sh`'s `t` alias, etc.). The new file also fixes a
  double-`theme.sh`-restore bug in the `su`/`sudo`/`ssh` wrapper functions
  on Ctrl-C, and disowns a background watcher job in `sudo()` that could
  otherwise outlive its subshell.

## 0.3.1

- The live ISO's GRUB menu gains a **"memory test (memtest86+)"** entry
  when the build host has `memtest86+` installed. memtest is a standalone
  image, not a kernel, so BIOS loads it with `linux16` and UEFI chainloads
  the `memtest86+-efi` build; each entry is wrapped in a `${grub_platform}`
  guard so a machine only ever sees the one it can boot. The UEFI image is
  unsigned and needs Secure Boot disabled. `memtest86+` and `memtest86+-efi`
  are optional build-host packages -- when neither is present the entry is
  omitted and the build still succeeds. `doctor` reports what it finds.

## 0.3.0

- The live ISO's GRUB menu now ends with a **"safe graphics (nomodeset)"**
  entry: the newest kernel booted with `nomodeset` and without `quiet`, so
  it stays visible if it fails. It rescues machines that show a black or
  garbled screen on the normal entry (older Intel/NVIDIA laptops, some
  hybrid-graphics setups) -- the same fallback every mainstream distro ISO
  ships. Purely additive: `set default=0` still selects the normal boot.
- `create` no longer fails at the EFI-boot step with `mount: ... failed to
  set up loop device for .../efi.img` (exit 32). The FAT `efi.img` was
  populated by loop-mounting it, which needs root, the `loop` kernel
  module loaded, and a free loop device -- none of which is guaranteed on
  a host that was just updated to a new kernel and not yet rebooted, or
  one whose loop devices are all in use. It is now filled with `mtools`
  (`mmd` / `mcopy`), the same way archiso builds its `efiboot.img`, so no
  loop mount is involved. Adds a runtime dependency on `mtools`; `doctor`
  checks for it.

## 0.2.9

- `create` no longer fails when `calamares` is not installed on the build
  host. `calamares` is the live-ISO installer and is normally removed once
  Mabox is installed to disk, so most build hosts don't have it; previously
  `create` crashed with a bare `[Errno 2] No such file or directory:
  '/usr/share/calamares/settings.conf'` (or `.../calamares-branding`) part
  way through the build. It now detects the missing installer, skips every
  Calamares branding/config step, and builds a **live-only** ISO (boots to
  a live session, no installer), printing a clear notice in the build
  summary / `--explain` output. `doctor` reports the same. Install
  `calamares` first for an installable ISO. `create --encrypt` still
  requires `calamares` and errors early without it -- an encrypted ISO
  exists to be installed from, not booted live.

- The packaged `/etc/mabox-snapshot/images/` directory (drop `splash.png`
  here for a custom GRUB boot-menu background) is now created by the
  package instead of only being mentioned in the man page.

- The Calamares installer's welcome screen and window title now show the
  real Mabox release and codename (e.g. "Mabox Linux 26.08 Istredd")
  instead of a hardcoded "1.0". The shipped `branding.desc` keeps a `1.0`
  placeholder; `create` rewrites its `version` / `versionedName` strings
  from the build host's `/etc/lsb-release` (`DISTRIB_RELEASE` +
  `DISTRIB_CODENAME`) at build time -- Mabox's `/etc/os-release` carries
  no version field at all, and Calamares' own `branding.desc` substitution
  only reads `os-release`. Applied in both modes (reset via the overlay
  copy, preserving via a rendered workdir copy injected as an mksquashfs
  pseudo-file); falls back to the shipped placeholder if `/etc/lsb-release`
  is missing the fields. `--dry-run` and `--explain` show the resolved
  name.

- `create` now checks for the packaged Calamares branding assets
  (`/usr/share/mabox-snapshot/calamares-branding/`) up front, before the
  root prompt and workdir wipe, and `doctor` reports on them too. A stale
  or partial install that was missing just that directory previously
  failed mid-build with a bare `[Errno 2] No such file or directory`;
  both commands now say what is wrong and that reinstalling the package
  fixes it.

## 0.2.8

- Both build modes now ship Mabox's own Calamares installer branding
  (logo, sidebar colors, slideshow) instead of falling back to stock
  Manjaro branding. Previously this was a builder-configurable
  `slide-*.png` + `branding.toml` layer under
  `/etc/mabox-snapshot/images/` that shipped with no defaults, so every
  build silently showed Manjaro's branding unless someone configured it
  by hand. Replaced with Mabox's real, already-proven branding assets
  (extracted from a running Mabox VM's own `/etc/calamares/branding`)
  as a static package asset at
  `/usr/share/mabox-snapshot/calamares-branding/`, applied
  unconditionally: reset mode via an overlay copy
  (`calamares.write_branding()`), preserving mode -- which has no
  overlay step -- via mksquashfs pseudo-files straight into the rootfs
  layer (`calamares.build_branding_pseudo_specs()`), confirmed fixing a
  real build where preserving-mode installs still showed Manjaro
  branding after reset mode was already fixed.

## 0.2.7

- Cleanup pass ahead of external review: removed dead code with zero
  remaining references (`squashfs.available_compressors()`,
  `SnapshotConfig.demo_lang`, `constants.SUPPORTED_DEMO_LANGS`/
  `DEFAULT_DEMO_LANG`, `constants.CALAMARES_CONFIG_DIR`), and fixed docs
  that still described persistence as unverified/not-yet-implemented after
  0.2.6 shipped it confirmed working on real hardware (`miso_persist`'s
  header comment, the persistent-usb design spec, and `SOURCES.md`, which
  was missing attribution for the `miso_boot` hook vendored in 0.2.6). No
  behavior changes.

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
