"""Every hardcoded Mabox/Manjaro filesystem path, in one place."""

from pathlib import Path

# /etc/os-release on Mabox has no distinct ID (ID=manjaro) -- match on NAME instead.
OS_RELEASE_FILE = Path("/etc/os-release")
OS_RELEASE_NAME_MARKER = "Mabox"

# /etc/lsb-release carries the Mabox release + codename (DISTRIB_RELEASE,
# DISTRIB_CODENAME) that /etc/os-release lacks entirely on Mabox (ID=manjaro,
# BUILD_ID=rolling, no VERSION*). Calamares' branding.desc only substitutes
# strings from os-release, never lsb-release, so calamares.render_branding_desc()
# reads this at build time to bake the real versioned name into the installer
# branding instead of shipping branding.desc's "1.0" placeholder.
LSB_RELEASE_FILE = Path("/etc/lsb-release")

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

# Per-user, not per-system: a reset's pre-overwrite backup (and any named
# template saved via 'excludes backups save <name>') is the invoking user's
# own customization history, not shipped/system config -- lives under their
# real home (see privilege.resolve_effective_home()), joined to this at
# call time, not a standalone absolute path like the /etc ones above.
EXCLUDES_BACKUPS_DIRNAME = Path(".config/mabox-snapshot/excludes-backups")

NAMED_FOLDERS = ["Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos", "Public", "Templates"]

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
# miso boot hook to run, except "miso" itself is replaced with "miso_boot"
# (see configs/initcpio/{hooks,install}/miso_boot): a vendored copy of the
# external package's own hook, carrying only a fix to _find_dev_by_path()'s
# boot-device resolution (prefers a real partition over the whole disk --
# see that file's header comment for why). mkinitcpio resolves
# /etc/initcpio/{hooks,install}/ before /usr/lib/initcpio/{hooks,install}/,
# so the fix can't be vendored under the external hook's own name; needs a
# distinct one instead, exactly like miso_luks below. miso_persist MUST stay
# listed after miso_loop_mnt/miso_pxe_* -- each of those conditionally
# overwrites mount_handler for its own alt-boot-source (img_loop=, PXE net
# params); miso_persist chains onto whatever mount_handler is set at the
# time its own run_hook() runs, so loading before them would have its
# wrapping silently discarded whenever one of those paths triggers. See
# configs/initcpio/hooks/miso_persist's header comment for the full story.
MKINITCPIO_MISO_MODULES = ["loop", "dm-snapshot"]
MKINITCPIO_MISO_HOOKS = [
    "base", "udev", "miso_shutdown", "miso_boot", "miso_loop_mnt",
    "miso_pxe_common", "miso_pxe_http", "miso_pxe_nbd", "miso_pxe_nfs",
    "miso_persist", "miso_kms", "modconf", "block", "filesystems", "keyboard", "keymap",
]

# --encrypt builds only (preserving mode, opt-in): a wholly separate hook
# name and HOOKS/MODULES pair from the ones above -- never both listed
# together -- so this new, root-and-VM-only-verifiable path can't regress
# the already-working unencrypted boot chain. See mabox_snapshot/luks.py
# and configs/initcpio/{hooks,install}/miso_luks (a modified copy of the
# stock miso hook, not a hook layered before it -- the decrypt step has to
# happen inside miso_mount_handler()'s per-layer loop). Carries the same
# _find_dev_by_path() boot-device-resolution fix as miso_boot above -- keep
# the two in sync by hand.
MKINITCPIO_MISO_LUKS_MODULES = ["loop", "dm-snapshot", "dm-crypt"]
MKINITCPIO_MISO_LUKS_HOOKS = [
    "base", "udev", "miso_shutdown", "miso_luks", "miso_loop_mnt",
    "miso_pxe_common", "miso_pxe_http", "miso_pxe_nbd", "miso_pxe_nfs",
    "miso_persist", "miso_kms", "modconf", "block", "filesystems", "keyboard", "keymap",
]

# Installed by packaging/PKGBUILD alongside the package itself -- the only
# signal cli.py has that an --encrypt build is possible on this host (same
# precedent as seed.py's MABOX_SKEL_DIR check).
MISO_LUKS_HOOK_INSTALLED = Path("/usr/lib/initcpio/hooks/miso_luks")

# Vendored by this package (like miso_luks above and miso_persist below, not
# manjaro-tools-iso-git) -- see MKINITCPIO_MISO_HOOKS above for why. Checked
# the same way MISO_PERSIST_HOOK_INSTALLED is below (see
# isobuild.check_miso_boot_hook_installed()).
MISO_BOOT_HOOK_INSTALLED = Path("/usr/lib/initcpio/hooks/miso_boot")

# Persistent-USB boot hook (see configs/initcpio/{hooks,install}/
# miso_persist and docs/superpowers/specs/2026-08-20-persistent-usb-design.md).
# Always included in both HOOKS lists above -- unlike miso_luks, there is no
# unencrypted/encrypted split to make here: miso_persist is a no-op at boot
# whenever no MABOX_PERSIST partition is found, so shipping it unconditionally
# is safe. Vendored by this package (like miso_luks, not manjaro-tools-iso-git)
# -- installed by packaging/PKGBUILD, checked the same way
# MISO_LUKS_HOOK_INSTALLED is (see isobuild.check_miso_persist_hook_installed()),
# just unconditionally rather than only under --encrypt.
MISO_PERSIST_HOOK_INSTALLED = Path("/usr/lib/initcpio/hooks/miso_persist")

# Cross-repo contract with mabox-persistence-usb's isoinspect.
# evaluate_hook_support(): a plain-text version marker written inside the
# ISO9660 tree (see isobuild.write_persist_hook_marker()), parallel to
# assemble()'s existing ".miso" marker convention -- lets that tool tell
# whether an ISO's initramfs actually includes miso_persist without
# decompressing and walking the initramfs cpio itself. Must stay in sync by
# hand with mabox_persistence_usb.constants.PERSIST_HOOK_MARKER_PATH /
# MIN_SUPPORTED_HOOK_VERSION -- the two repos share no runtime code, same
# manual-sync precedent as ISO_VOLID above. Treated as one monotonically
# increasing cumulative-capability counter, not independent flags: v1
# shipped miso_persist, but boot-device resolution always picked the whole
# disk over any partition of the same device, so persistence never actually
# activated at boot; v2 (this version) fixes that -- see miso_boot's and
# miso_luks's _find_dev_by_path() -- so plain MABOX_PERSIST now actually
# mounts read-write. A future v3 would add a LUKS-unlock branch to
# miso_persist for --encrypt-persist.
PERSIST_HOOK_MARKER_RELPATH = Path(MISO_BASEDIR) / ".persist-hook-version"
PERSIST_HOOK_VERSION = 2

# Everything MKINITCPIO_MISO_HOOKS/MKINITCPIO_MISO_LUKS_HOOKS reference that
# isn't a stock mkinitcpio hook and isn't miso_luks or miso_boot (vendored
# above): comes from manjaro-tools-iso-git, which packaging/PKGBUILD does
# NOT depend on (see SOURCES.md). Missing on a host without it, so
# build_initramfs() would otherwise fail deep inside mkinitcpio -- after the
# expensive mksquashfs step -- with a bare CalledProcessError instead of a
# clear message. Checked against install/, not hooks/: mkinitcpio's own
# run_build_hook() (see /usr/lib/initcpio/functions) resolves a hook by
# searching ONLY $_d_install ("/etc/initcpio/install:/usr/lib/initcpio/
# install" by default) for a same-named install script -- that's the
# literal source of its "Hook 'X' cannot be found" error. The separate
# hooks/ runtime script is optional and install-only hooks are normal
# (miso_kms is one: it just loads DRM/KMS modules early, no runtime action
# needed, same shape as mkinitcpio's own stock "kms" hook) -- checking
# hooks/ instead produced a false "missing" for miso_kms on a host where it
# was correctly installed.
MISO_EXTERNAL_HOOKS = [
    "miso_shutdown", "miso_loop_mnt", "miso_pxe_common",
    "miso_pxe_http", "miso_pxe_nbd", "miso_pxe_nfs", "miso_kms",
]
MISO_HOOK_SEARCH_DIRS = [Path("/etc/initcpio/install"), Path("/usr/lib/initcpio/install")]

# add_binary calls inside the miso hooks' own install scripts (see e.g.
# /etc/initcpio/install/miso_pxe_http and .../miso_pxe_nbd) -- found by
# reading every miso install script mkinitcpio actually runs. Neither
# binary is pulled in by manjaro-tools-iso-git or anything else this
# package depends on (that package ships the install SCRIPTS, not what
# they shell out to at build time), so a host missing either one hits
# mkinitcpio's own "binary not found" error deep inside
# build_initramfs() -- after the expensive mksquashfs step, same failure
# mode MISO_EXTERNAL_HOOKS above already guards against for the hook
# scripts themselves. curl -> miso_pxe_http, nbd-client -> miso_pxe_nbd.
MISO_EXTERNAL_BINARIES = ["curl", "nbd-client"]

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

# GRUB splash source, user-configurable (see cli.py's splash_source /
# has_splash) -- plain directory under /etc/mabox-snapshot, same
# convention as EXCLUDES_LIST_FILE, no separate per-user split. Calamares
# branding used to read a slide-*.png + branding.toml pair from here too;
# now a static packaged asset instead (see CALAMARES_BRANDING_SRC below)
# -- Mabox's own branding isn't something meant to vary per build.
IMAGES_DIR = Path("/etc/mabox-snapshot/images")

# Verified on this host: the *installed* calamares package already ships a
# complete, safe settings.conf + module confs at CALAMARES_SETTINGS_FILE's
# directory. This tool only ever swaps *which branding component*
# settings.conf points at (to CALAMARES_BRANDING_COMPONENT, populated from
# CALAMARES_BRANDING_SRC -- reset mode via calamares.py's write_branding(),
# preserving mode via its build_branding_pseudo_specs()); the install
# sequence itself (partition/bootloader/users/...) is never touched.
CALAMARES_SETTINGS_FILE = Path("/usr/share/calamares/settings.conf")
CALAMARES_BRANDING_COMPONENT = "mabox"

# Mabox's actual Calamares branding -- branding.desc, show.qml, and their
# slideshow/logo images, the same assets that produce Mabox's own
# live-ISO install branding (extracted from a running Mabox VM's
# /etc/calamares/branding/manjaro). Deliberately static, not
# builder-configurable: this is an official Mabox tool now, not a
# generic remaster utility, so one fixed identity beats a
# template/config layer nobody was actually using. Installed by the
# package (see packaging/PKGBUILD); vendored copy in
# configs/calamares-branding/ during development.
CALAMARES_BRANDING_SRC = SHARE_DIR / "calamares-branding"
