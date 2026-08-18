# mabox-snapshot

Snapshot a running [Mabox Linux](https://maboxlinux.org/) system into a bootable live/install ISO. Mabox-only, Python, CLI-only — modeled on MX Linux's `mx-snapshot`, not a port of it.

**Status: core build pipeline (both modes) is code-complete, unverified by a real boot.** See the project plan for design and build order — the one remaining step before trusting any of this is booting a produced ISO in a VM.

## Two modes

- **`preserving`** — a full personal clone: real `/home`, real accounts, real passwords. For migrating to new hardware or backing up your own machine. Not for sharing. Optionally LUKS2-encrypted (`--encrypt`).
- **`reset`** — a sanitized ISO for sharing: a synthetic `demo`/`demo` account replaces the real user, no real `/home`, no saved network credentials, no machine ID.

Both modes support a user-editable include/exclude list, so you control what's carried into the snapshot beyond the defaults.

## Why not just use `mx-snapshot`?

`mx-snapshot` (and its Arch-based `MXarch` variant) already does something close to this, and is a real reference for this project's design. But it assumes vanilla Arch — Mabox is Manjaro-based, with its own repo layering, versioned multi-kernel packaging, and its own desktop bootstrap (jgmenu/tint2/openbox) that a generic Arch tool doesn't know about. `mabox-snapshot` exists to get those specifics right for this one distro.

## Testing in a VM

Boot-testing a produced ISO is required before trusting it (see the project plan's verification tiers) — [quickemu](https://github.com/quickemu-project/quickemu) with a SPICE display works well for this. For clipboard/resolution/mouse integration and clean host↔guest shutdown inside the guest, install and enable:

- `spice-vdagent` (`spice-vdagentd.service`) — SPICE display integration.
- `qemu-guest-agent` (`qemu-guest-agent.service`) — host↔guest communication (graceful shutdown, guest info queries).


## Some commands

```
mabox-snapshot -h

usage: mabox-snapshot [-h] {version,doctor,create,config,excludes,packages} ...

positional arguments:
  {version,doctor,create,config,excludes,packages}
    version             Print the version
    doctor              Check prerequisites, read-only
    create              Build a snapshot
    config              Inspect or edit configuration
    excludes            Manage the exclude list
    packages            Inspect installed packages

options:
  -h, --help            show this help message and exit

✔ ~/Github/archcanary [master ↓·3|✔] 
10:43 $ mabox-snapshot create --help
usage: mabox-snapshot create [-h] --mode {preserving,reset} [-w WORKDIR] [-o] [-m] [--output-dir OUTPUT_DIR] [--iso-name ISO_NAME]
                             [--compression {zstd,xz,lz4,lzo,gzip}] [--compression-level COMPRESSION_LEVEL] [--exclude-list EXCLUDE_LIST]
                             [--exclude-folder {Desktop,Documents,Downloads,Music,Pictures,Videos,Public,Templates}] [--kernel KERNEL] [--all-kernels]
                             [--dry-run] [--keep-workdir] [--max-age-days MAX_AGE_DAYS] [--change-threshold-mb CHANGE_THRESHOLD_MB] [--encrypt]
                             [--backup-to BACKUP_TO]

Build a bootable live/install ISO from the running system.

options:
  -h, --help            show this help message and exit
  --mode {preserving,reset}
                        preserving: full personal clone (real /home, real accounts, real passwords; optionally --encrypt). reset: sanitized ISO for sharing
                        (synthetic demo/demo account, no real /home, no saved credentials)
  -w, --workdir WORKDIR
                        Scratch directory for build state -- squashfs layers, ISO tree, mkinitcpio config (default: /var/lib/mabox-snapshot/work)
  -o, --skip-space-check
                        Skip the free-space precheck on workdir/output-dir before building
  -m, --month           Name the output by year-month instead of a full timestamp
  --output-dir OUTPUT_DIR
                        Directory the finished ISO is written to (default: same as --workdir)
  --iso-name ISO_NAME   Base filename for the ISO, without .iso (default: mabox-<mode>-<timestamp>)
  --compression {zstd,xz,lz4,lzo,gzip}
                        Squashfs compression algorithm passed to mksquashfs -comp (default: zstd)
  --compression-level COMPRESSION_LEVEL
                        Compression level passed to mksquashfs -Xcompression-level (valid range depends on --compression; default: mksquashfs's own
                        default)
  --exclude-list EXCLUDE_LIST
                        Path to a custom exclude-pattern file, replacing the default list (default: /etc/mabox-snapshot/excludes.list)
  --exclude-folder {Desktop,Documents,Downloads,Music,Pictures,Videos,Public,Templates}
                        Exclude a named XDG user folder from the snapshot in addition to --exclude-list; repeatable
  --kernel KERNEL       Only include this installed kernel, matched against mkinitcpio presets (default: newest installed kernel)
  --all-kernels         Include every installed kernel instead of just the newest
  --dry-run             Print the resolved plan and command, execute nothing
  --keep-workdir        No-op for now: workdir cleanup isn't implemented yet, so build state under --workdir is always kept
  --max-age-days MAX_AGE_DAYS
                        Delete older mabox-*.iso files in the output dir after a successful build
  --change-threshold-mb CHANGE_THRESHOLD_MB
                        Prompt about home-dir items new/grown by at least this many MiB since the last snapshot (default 200)
  --encrypt             Encrypt rootfs.sfs with LUKS2 (preserving mode only; passphrase prompted interactively at build time)
  --backup-to BACKUP_TO
                        rsync the finished ISO here (local path or user@host:path); repeatable

example:
  mabox-snapshot create --mode reset --output-dir /mnt/usb --all-kernels
```

## License

MIT — see [LICENSE](LICENSE).

## Credits / references

Design references only, not vendored code unless explicitly noted (e.g. `configs/mabox-skel/`) — see [SOURCES.md](SOURCES.md).
