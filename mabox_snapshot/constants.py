"""Every hardcoded Mabox/Manjaro filesystem path, in one place."""

from pathlib import Path

# /etc/os-release on Mabox has no distinct ID (ID=manjaro) -- match on NAME instead.
OS_RELEASE_FILE = Path("/etc/os-release")
OS_RELEASE_NAME_MARKER = "Mabox"

SYSTEM_CONFIG_FILE = Path("/etc/mabox-snapshot/mabox-snapshot.conf")
USER_CONFIG_FILE = Path("~/.config/mabox-snapshot/mabox-snapshot.conf").expanduser()
EXCLUDES_LIST_FILE = Path("/etc/mabox-snapshot/excludes.list")
EXCLUDES_LIST_DEFAULT = Path("/usr/share/mabox-snapshot/excludes.list.default")

# Separate, additive, power-user file for ordered include/exclude override
# rules (see excludes.py's OverrideRuleList/compile_override_rules) -- kept
# apart from EXCLUDES_LIST_FILE's flat, unordered, pure-exclude patterns
# rather than retrofitting a breaking format change onto it. Empty/absent
# by default, no shipped default to reset to.
OVERRIDE_RULES_FILE = Path("/etc/mabox-snapshot/overrides.list")

NAMED_FOLDERS = ["Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos", "Public", "Templates"]

# Shared by cli.py's default --iso-name and retention.py's prune glob, so the
# two can't drift apart.
ISO_NAME_PREFIX = "mabox-"

DEFAULT_WORKDIR = Path("/var/lib/mabox-snapshot/work")

# Per-run snapshot manifests (see history.py) -- one small hand-written TOML
# file per successful `create`, named after its ISO's own filename stem.
# Same /var/lib placement as DEFAULT_WORKDIR: runtime-generated state, not
# user config.
HISTORY_DIR = Path("/var/lib/mabox-snapshot/history")

# Installed by the package (see packaging/PKGBUILD); vendored copies live in
# configs/ during development.
SHARE_DIR = Path("/usr/share/mabox-snapshot")
MABOX_SKEL_DIR = SHARE_DIR / "mabox-skel" / "skel"
CALAMARES_CONFIG_DIR = SHARE_DIR / "calamares"

# pacman/system files copied verbatim into every snapshot (both modes -- no
# personal data in either).
PACMAN_CONF = Path("/etc/pacman.conf")
PACMAN_MIRRORLIST = Path("/etc/pacman.d/mirrorlist")
FSTAB_FILE = Path("/etc/fstab")
MOUNTS_FILE = Path("/proc/mounts")

# The only other mounted filesystems the rootfs layer's scan of '/' is
# allowed to cross into -- standard FHS top-level directories Calamares's
# manual partitioning lets a user put on their own partition, not
# incidental/removable storage. Everything else mounted under '/' (backup
# drives, USB sticks, custom data volumes, etc.) is excluded wholesale by
# excludes.detect_foreign_mount_excludes() so a snapshot never silently
# balloons to include unrelated mounted volumes. A tuple, not a list --
# it's used as a function default argument and must not be mutable.
ALLOWED_ROOTFS_MOUNTS = (
    Path("/boot"), Path("/home"), Path("/var"), Path("/usr"),
    Path("/opt"), Path("/srv"), Path("/root"),
)

# Kernel-provided virtual filesystems -- never real persistent data, no
# matter where an application chooses to mount one. Matched by fstype
# instead of mountpoint, so it's caught even when nested under an
# otherwise-allowed path -- confirmed against a real snapshot build: PIA
# VPN mounts its own cgroup v1 net_cls controller at
# /opt/piavpn/etc/cgroup/net_cls, which slipped past
# ALLOWED_ROOTFS_MOUNTS's is_relative_to(/opt) check entirely (that check
# only cares about the mountpoint's path, not what's actually mounted
# there) and got squashed as if it were real data -- mksquashfs couldn't
# even read several of its control files ("Failed to read file
# .../cgroup.procs, creating empty file"), since cgroupfs entries aren't
# regular readable files at all.
PSEUDO_FILESYSTEM_TYPES = frozenset({
    "proc", "sysfs", "cgroup", "cgroup2", "devpts", "devtmpfs", "mqueue",
    "pstore", "securityfs", "debugfs", "tracefs", "configfs", "fusectl",
    "binfmt_misc", "rpc_pipefs", "nsfs", "autofs",
})

# Reset-mode-only: excluded from the rootfs layer outright, then replaced
# with sanitized versions from the overlay layer (see sanitize.py) --
# excluded here too, not just overridden, so the real password hashes are
# never present on the ISO at all, not merely shadowed by the boot-time
# overlay. Paths are relative to '/', matching mksquashfs -ef.
RESET_MODE_ONLY_EXCLUDES = [
    "home/*",
    "etc/passwd",
    "etc/shadow",
    "etc/gshadow",
    "etc/group",
    "etc/subuid",
    "etc/subgid",
    "etc/machine-id",
    "etc/NetworkManager/system-connections/*",
]

DEMO_USERNAME = "demo"
DEMO_UID = 1000
DEMO_GID = 1000
DEMO_BASELINE_GROUPS = ["wheel", "audio", "video", "storage", "optical", "network"]

REQUIRED_TOOLS = ["mksquashfs", "xorriso", "grub-mkimage", "mkinitcpio", "mkfs.fat", "rsync", "openssl"]
OPTIONAL_TOOLS = ["calamares", "yay", "magick", "cryptsetup"]

SUPPORTED_DEMO_LANGS = ["en", "es", "pl"]
DEFAULT_DEMO_LANG = "en"

# ISO boot layout, modeled on Manjaro's own miso hook (verified on this host
# at /etc/initcpio/hooks/miso -- misobasedir defaults to "manjaro" there if
# unset, but every build below passes it explicitly to avoid relying on that
# default). ISO_VOLID doubles as the misolabel= kernel param so the live
# hook can find its boot device via /dev/disk/by-label/<volid>.
MISO_BASEDIR = "mabox"
ISO_VOLID = "MABOX_LIVE"
ISO_ARCH = "x86_64"

GRUB_LIB_DIR = Path("/usr/lib/grub")

# GRUB's own bundled font, shipped by the grub package itself (confirmed:
# `pacman -Qo` on this host resolves it to package grub, not something
# ad-hoc) -- without an explicit loadfont, gfxterm falls back to whatever
# minimal font is built into the boot image, which lacks glyphs for the
# Unicode box-drawing characters GRUB's own default bordered-menu style
# uses, rendering as placeholder boxes instead of a clean border.
GRUB_UNICODE_FONT = Path("/usr/share/grub/unicode.pf2")

# Verified at /usr/share/manjaro-tools/mkinitcpio.conf (manjaro-tools-iso-git
# package) -- the exact HOOKS/MODULES a live ISO's initramfs needs for the
# miso boot hook to run.
MKINITCPIO_MISO_MODULES = ["loop", "dm-snapshot"]
MKINITCPIO_MISO_HOOKS = [
    "base", "udev", "miso_shutdown", "miso", "miso_loop_mnt",
    "miso_pxe_common", "miso_pxe_http", "miso_pxe_nbd", "miso_pxe_nfs",
    "miso_kms", "modconf", "block", "filesystems", "keyboard", "keymap",
]

# --encrypt builds only (preserving mode, opt-in): a wholly separate hook
# name and HOOKS/MODULES pair from the ones above -- never both listed
# together -- so this new, root-and-VM-only-verifiable path can't regress
# the already-working unencrypted boot chain. See mabox_snapshot/luks.py
# and configs/initcpio/{hooks,install}/miso_luks (a modified copy of the
# stock miso hook, not a hook layered before it -- the decrypt step has to
# happen inside miso_mount_handler()'s per-layer loop).
MKINITCPIO_MISO_LUKS_MODULES = ["loop", "dm-snapshot", "dm-crypt"]
MKINITCPIO_MISO_LUKS_HOOKS = [
    "base", "udev", "miso_shutdown", "miso_luks", "miso_loop_mnt",
    "miso_pxe_common", "miso_pxe_http", "miso_pxe_nbd", "miso_pxe_nfs",
    "miso_kms", "modconf", "block", "filesystems", "keyboard", "keymap",
]

# Installed by packaging/PKGBUILD alongside the package itself -- the only
# signal cli.py has that an --encrypt build is possible on this host (same
# precedent as seed.py's MABOX_SKEL_DIR check).
MISO_LUKS_HOOK_INSTALLED = Path("/usr/lib/initcpio/hooks/miso_luks")

# Everything MKINITCPIO_MISO_HOOKS/MKINITCPIO_MISO_LUKS_HOOKS reference that
# isn't a stock mkinitcpio hook and isn't miso_luks (vendored above): comes
# from manjaro-tools-iso-git, which packaging/PKGBUILD does NOT depend on
# (see SOURCES.md). Missing on a host without it, so build_initramfs() would
# otherwise fail deep inside mkinitcpio -- after the expensive mksquashfs
# step -- with a bare CalledProcessError instead of a clear message.
# mkinitcpio itself resolves each hook name by searching /etc/initcpio then
# /usr/lib/initcpio, in that order, so either counts as "installed".
MISO_EXTERNAL_HOOKS = [
    "miso", "miso_shutdown", "miso_loop_mnt", "miso_pxe_common",
    "miso_pxe_http", "miso_pxe_nbd", "miso_pxe_nfs", "miso_kms",
]
MISO_HOOK_SEARCH_DIRS = [Path("/etc/initcpio/hooks"), Path("/usr/lib/initcpio/hooks")]

# Deliberately different from the plaintext "rootfs.sfs" name so the boot
# hook can unambiguously tell, from the filename alone, which case it's in.
LUKS_CONTAINER_SUFFIX = ".luks"

# dm-crypt mapper name -- used only transiently during the build (luks.py
# opens then closes it; never left attached) and hardcoded identically in
# configs/initcpio/hooks/miso_luks's _mnt_luks_sfs() for the boot-time
# open. The two never share a process, so this constant is a single
# source of truth to keep the shell copy in sync with, not a runtime link.
ISO_LUKS_MAPPER_NAME = "mabox_rootfs"

# Where Calamares' unpackfs module reads an --encrypt build's decrypted
# rootfs from, via a "file" sourcefs entry (see calamares.py's
# build_unpackfs_conf()). This is NOT the path miso_luks's _mnt_luks_sfs()
# itself mounts the decrypted rootfs at during boot (/run/miso/sfs/rootfs)
# -- that mount does not survive switch_root into the running system
# (verified empirically: it's an empty, orphaned directory afterward,
# even from PID 1's own mount namespace, even though the live session
# keeps working fine regardless, since overlayfs doesn't need that
# original mount path to stay valid once it's already built the live
# root from it). A first fix attempt remounted the still-unlocked
# dm-crypt device here via a systemd unit running once at boot -- also
# verified, the hard way, in a real VM, to be unreliable: the mount can
# go empty again well after boot, for reasons never fully pinned down,
# with no guarantee it's still there by whenever Calamares actually runs.
# The only mount that's provably valid is one made *immediately* before
# it's read, so this path is now provisioned by a Calamares shellprocess
# job (calamares.py's build_shellprocess_remount_conf()/
# insert_live_source_job()) spliced into the exec sequence right before
# unpackfs -- remount and read happen back to back, no gap for anything
# to disturb in between. No second passphrase prompt needed either way:
# the dm-crypt mapping (see ISO_LUKS_MAPPER_NAME) is already unlocked by
# the time either mechanism runs.
MISO_LUKS_LIVE_ROOTFS_MOUNT = "/run/mabox-snapshot/live-source"

# User-editable branding source, same convention as EXCLUDES_LIST_FILE
# (plain directory under /etc/mabox-snapshot, no separate per-user split).
# Verified on this host: the *installed* calamares package already ships a
# complete, safe settings.conf + module confs at CALAMARES_SETTINGS_FILE's
# directory (git.maboxlinux.org has no Mabox-specific Calamares repo, so
# there's nothing to vendor there -- Mabox installs just inherit stock
# Manjaro branding unless this tool overrides it). This tool only ever
# swaps *which branding component* settings.conf points at; the install
# sequence itself (partition/bootloader/users/...) is never touched.
IMAGES_DIR = Path("/etc/mabox-snapshot/images")
CALAMARES_SETTINGS_FILE = Path("/usr/share/calamares/settings.conf")
CALAMARES_BRANDING_COMPONENT = "mabox"
MABOX_LOGO_SVG = MABOX_SKEL_DIR / ".icons" / "mabox-logo-square.svg"
DEFAULT_CALAMARES_PRODUCT_NAME = "Mabox Linux"
DEFAULT_TEXT_RADIUS = 8
