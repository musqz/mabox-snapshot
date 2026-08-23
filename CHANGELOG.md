# Changelog

## Unreleased

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
