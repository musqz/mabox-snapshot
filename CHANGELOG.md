# Changelog

## Unreleased

- `create` now writes a `.sha256` checksum file alongside the built ISO by default; disable with
  `-n`/`--no-checksums`.
- Removed unattended systemd timer automation (`mabox-snapshot.service`/`.timer`) -- no longer
  shipped or packaged.

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
