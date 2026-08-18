# mabox-snapshot

Snapshot a running [Mabox Linux](https://maboxlinux.org/) system into a bootable live/install ISO. Mabox-only, Python, CLI-only — modeled on MX Linux's `mx-snapshot`, not a port of it.

**Status: core build pipeline (both modes) is code-complete, unverified by a real boot.** See the project plan for design and build order — the one remaining step before trusting any of this is booting a produced ISO in a VM.

## Two modes

- **`preserving`** — a full personal clone: real `/home`, real accounts, real passwords. For migrating to new hardware or backing up your own machine. Not for sharing. Optionally LUKS2-encrypted (`--encrypt`).
- **`reset`** — a sanitized ISO for sharing: a synthetic `demo`/`demo` account replaces the real user, no real `/home`, no saved network credentials, no machine ID.

Both modes support a user-editable exclude list (`excludes add/remove/edit`), plus ordered `excludes rules add exclude/include ...` overrides for keeping one specific subpath inside an otherwise-excluded directory (e.g. one folder under `Documents`), so you control what's carried into the snapshot beyond the defaults. `--profile {full,lean}` trades completeness for a smaller/faster build; `mabox-snapshot skel audit` shows which of your desktop config differs from Mabox's shipped defaults, to help decide what's worth protecting in a leaner profile.

## Why not just use `mx-snapshot`?

`mx-snapshot` (and its Arch-based `MXarch` variant) already does something close to this, and is a real reference for this project's design. But it assumes vanilla Arch — Mabox is Manjaro-based, with its own repo layering, versioned multi-kernel packaging, and its own desktop bootstrap (jgmenu/tint2/openbox) that a generic Arch tool doesn't know about. `mabox-snapshot` exists to get those specifics right for this one distro.

## Testing in a VM

Boot-testing a produced ISO is required before trusting it (see the project plan's verification tiers) — [quickemu](https://github.com/quickemu-project/quickemu) with a SPICE display works well for this. For clipboard/resolution/mouse integration and clean host↔guest shutdown inside the guest, install and enable:

- `spice-vdagent` (`spice-vdagentd.service`) — SPICE display integration.
- `qemu-guest-agent` (`qemu-guest-agent.service`) — host↔guest communication (graceful shutdown, guest info queries).

## License

MIT — see [LICENSE](LICENSE).

## Credits / references

Design references only, not vendored code unless explicitly noted (e.g. `configs/mabox-skel/`) — see [SOURCES.md](SOURCES.md).
