# mabox-snapshot

Snapshot a running [Mabox Linux](https://maboxlinux.org/) system into a bootable live/install ISO. Mabox-only, Python, CLI-only — modeled on MX Linux's `mx-snapshot`, not a port of it.

**Status: early development, not yet functional.** See the project plan for design and build order.

## Two modes

- **`preserving`** — a full personal clone: real `/home`, real accounts, real passwords. For migrating to new hardware or backing up your own machine. Not for sharing.
- **`reset`** — a sanitized ISO for sharing: a synthetic `demo`/`demo` account replaces the real user, no real `/home`, no saved network credentials, no machine ID.

Both modes support a user-editable include/exclude list, so you control what's carried into the snapshot beyond the defaults.

## Why not just use `mx-snapshot`?

`mx-snapshot` (and its Arch-based `MXarch` variant) already does something close to this, and is a real reference for this project's design. But it assumes vanilla Arch — Mabox is Manjaro-based, with its own repo layering, versioned multi-kernel packaging, and its own desktop bootstrap (jgmenu/tint2/openbox) that a generic Arch tool doesn't know about. `mabox-snapshot` exists to get those specifics right for this one distro.

## License

MIT — see [LICENSE](LICENSE).

## Credits / references

Design references only, not vendored code unless explicitly noted (e.g. `configs/mabox-skel/`) — see [SOURCES.md](SOURCES.md).
