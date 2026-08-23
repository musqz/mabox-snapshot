# mabox-snapshot

![Release](https://img.shields.io/github/v/release/musqz/mabox-snapshot.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-Mabox%20Linux-2f4f4f.svg)

Snapshot a running [Mabox Linux](https://maboxlinux.org/) system into a bootable live/install ISO. Mabox-only, Python, CLI-only — modeled on MX Linux's `mx-snapshot`, not a port of it.

## Two modes

- **`preserving`** — a full personal clone: real `/home`, real accounts, real passwords. For migrating to new hardware or backing up your own machine. Not for sharing. Optionally LUKS2-encrypted (`--encrypt`). Calamares' own account-creation step is skipped — the snapshot already *is* your account.
- **`reset`** — a sanitized ISO for sharing: a synthetic `demo`/`demo` account replaces the real user, no real `/home`, no saved network credentials, no machine ID.

Both modes support a user-editable exclude list (`excludes add/remove/edit`), plus ordered `excludes rules add exclude/include ...` overrides for keeping one specific subpath inside an otherwise-excluded directory (e.g. one folder under `Documents`), so you control what's carried into the snapshot beyond the defaults. `excludes reset` always backs up the list it's about to replace first, and `excludes backups save <name>` doubles as a reusable custom template you can `backups restore` later. `--profile {full,lean}` trades completeness for a smaller/faster build; `mabox-snapshot skel audit` shows which of your desktop config differs from Mabox's shipped defaults, to help decide what's worth protecting in a leaner profile.

## Why not just use `mx-snapshot`?

`mx-snapshot` (and its Arch-based `MXarch` variant) already does something close to this, and is a real reference for this project's design. But it assumes vanilla Arch — Mabox is Manjaro-based, with its own repo layering, versioned multi-kernel packaging, and its own desktop bootstrap (jgmenu/tint2/openbox) that a generic Arch tool doesn't know about. `mabox-snapshot` exists to get those specifics right for this one distro.

## Installation

Arch/Manjaro-based only (Mabox itself, or any Arch derivative with the same dependencies).

```sh
git clone https://github.com/musqz/mabox-snapshot.git
cd mabox-snapshot/packaging
makepkg -si
```

Runtime dependencies (`squashfs-tools`, `grub`, `mkinitcpio`, `libisoburn`, `dosfstools`, `rsync`, `openssl`) are pulled in automatically. `calamares` is an optional dependency — only needed if the produced ISO will be installed *from*, not just booted live; `cryptsetup` is optional too, needed only for `--encrypt` builds.

## Quick start

```sh
mabox-snapshot doctor                                             # check prerequisites, read-only, no root needed
sudo mabox-snapshot create preserving --output-dir /mnt/usb --encrypt
```

## Usage

Full command reference: `man mabox-snapshot`, installed with the package. Bash tab-completion is
also installed (needs the optional `bash-completion` package to be active).

```
usage: mabox-snapshot [-h]
                       {version,doctor,create,config,excludes,packages,skel} ...

positional arguments:
  {version,doctor,create,config,excludes,packages,skel}
    version             Print the version
    doctor              Check prerequisites, read-only
    create              Build a snapshot
    config              Inspect or edit configuration
    excludes            Manage the exclude list
    packages            Inspect installed packages
    skel                Compare your desktop config against Mabox's shipped
                        defaults

options:
  -h, --help            show this help message and exit
```

`create` is the main command:

```
usage: mabox-snapshot create [-h] [-w WORKDIR] [-o]
                              [--output-dir OUTPUT_DIR]
                              [--iso-name ISO_NAME]
                              [--compression {zstd,xz,lz4,lzo,gzip}]
                              [--compression-level COMPRESSION_LEVEL]
                              [--exclude-list EXCLUDE_LIST]
                              [--exclude-folder {Desktop,Documents,Downloads,Music,Pictures,Videos,Public,Templates}]
                              [--kernel KERNEL] [--all-kernels] [--dry-run]
                              [--change-threshold-mb CHANGE_THRESHOLD_MB]
                              [--encrypt] [--profile {full,lean}] [-n]
                              {preserving,reset}

Build a bootable live/install ISO from the running system.

positional arguments:
  {preserving,reset}    preserving: full personal clone (real /home, real
                        accounts, real passwords; optionally --encrypt).
                        reset: sanitized ISO for sharing (synthetic demo/demo
                        account, no real /home, no saved credentials)

options:
  -h, --help            show this help message and exit
  -w, --workdir WORKDIR
                        Scratch directory for build state -- squashfs layers,
                        ISO tree, mkinitcpio config (default: /var/lib/mabox-
                        snapshot/work)
  -o, --skip-space-check
                        Skip the free-space precheck on workdir/output-dir
                        before building
  --output-dir OUTPUT_DIR
                        Directory the finished ISO is written to (default:
                        same as --workdir)
  --iso-name ISO_NAME   Base filename for the ISO, without .iso (default:
                        mabox-<mode>-<timestamp>)
  --compression {zstd,xz,lz4,lzo,gzip}
                        Squashfs compression algorithm passed to mksquashfs
                        -comp (default: zstd, the best speed/ratio balance for
                        most builds). xz compresses smallest but slowest; gzip
                        is a universal fallback with a weaker ratio; lz4/lzo
                        are fastest but produce the largest output
  --compression-level COMPRESSION_LEVEL
                        Compression level passed to mksquashfs -Xcompression-
                        level. Only zstd (1-22, default 15), gzip (1-9,
                        default 9), and lzo (1-9, default 8) support this --
                        xz and lz4 have no such option in mksquashfs and will
                        error if a level is given
  --exclude-list EXCLUDE_LIST
                        Path to a custom exclude-pattern file, replacing the
                        default list (default: /etc/mabox-
                        snapshot/excludes.list)
  --exclude-folder {Desktop,Documents,Downloads,Music,Pictures,Videos,Public,Templates}
                        Exclude a named XDG user folder from the snapshot in
                        addition to --exclude-list; repeatable
  --kernel KERNEL       Only include this installed kernel, matched against
                        mkinitcpio presets (default: newest installed kernel)
  --all-kernels         Include every installed kernel instead of just the
                        newest
  --dry-run             Print the resolved plan and command, execute nothing
  --change-threshold-mb CHANGE_THRESHOLD_MB
                        Prompt about home-dir items new/grown by at least this
                        many MiB since the last snapshot (default 200)
  --encrypt             Encrypt rootfs.sfs with LUKS2 (preserving mode only;
                        passphrase prompted interactively at build time)
  --profile {full,lean}
                        Size/completeness tier: full (default, today's
                        behavior) or lean (trims unselected kernels' module
                        trees plus VM/container storage; see 'mabox-snapshot
                        skel audit' to curate further)
  -n, --no-checksums    Skip writing a .sha256 checksum file alongside the ISO

example:
  mabox-snapshot create reset --output-dir /mnt/usb --all-kernels
```

The other subcommands are smaller, self-explanatory surfaces — run any of them with `-h`:

| Command | Purpose |
|---|---|
| `config show` / `path` / `set` | Inspect or edit the resolved TOML configuration |
| `excludes list` / `edit` / `add` / `remove` / `reset` / `folders` / `rules` | Manage what's excluded from a snapshot |
| `packages list` | List installed packages, read-only, no root |
| `skel audit` | Show which desktop config files differ from Mabox's shipped defaults |
| `doctor` | Check prerequisites, read-only, no root |

## Custom GRUB splash

Drop a PNG at `/etc/mabox-snapshot/images/splash.png` and it's automatically resized/cropped to 1920x1080 and used as the GRUB boot menu's background. If it's missing, the ISO just gets a plain GRUB menu -- no error.

## Testing in a VM

Boot-testing a produced ISO before trusting it — [quickemu](https://github.com/quickemu-project/quickemu) with a SPICE display works well for this. For clipboard/resolution/mouse integration and clean host↔guest shutdown inside the guest, install and enable:

- `spice-vdagent` (`spice-vdagentd.service`) — SPICE display integration.
- `qemu-guest-agent` (`qemu-guest-agent.service`) — host↔guest communication (graceful shutdown, guest info queries).

## License

MIT — see [LICENSE](LICENSE).

## Credits / references

Design references only, not vendored code unless explicitly noted (e.g. `configs/mabox-skel/`) — see [SOURCES.md](SOURCES.md).
