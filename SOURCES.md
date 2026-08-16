# Sources

Design and technique references used while building this tool. None of this code is vendored or copied verbatim unless a specific file says otherwise (e.g. `configs/mabox-skel/`, which is a synced copy of an upstream repo) — this project is a from-scratch Python implementation.

- **[MX-Linux/mx-snapshot](https://github.com/MX-Linux/mx-snapshot)** (forked from [AdrianTM/mx-snapshot](https://github.com/AdrianTM/mx-snapshot), GPLv3) — the reference for the two-mode (`preserving`/`reset`) design, the exclude-list mechanism, and the reset-mode sanitization approach (synthetic `demo` account, `openssl passwd -6` rehash, `/etc/machine-id` handling).
- **`manjaro-tools-iso`** (installed on Mabox via `manjaro-tools-iso-git`) — `/usr/lib/manjaro-tools/util-iso.sh` and `util-iso-boot.sh` are the reference for the xorriso/grub-mkimage hybrid BIOS+UEFI ISO assembly; `/etc/initcpio/hooks/miso` is the reference live-boot mkinitcpio hook.
- **[Mabox/mabox-skel](https://git.maboxlinux.org/Mabox/mabox-skel)** — Mabox's own official `/etc/skel` template (jgmenu/tint2/openbox/theme defaults for a new user). Synced into `configs/mabox-skel/` as the source for reset-mode's demo-account desktop seeding.
- **[Mabox/manjaro-tools-livecd](https://git.maboxlinux.org/Mabox/manjaro-tools-livecd)** — reference for Mabox's own Calamares module configuration.
