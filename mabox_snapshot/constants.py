"""Every hardcoded Mabox/Manjaro filesystem path, in one place."""

from pathlib import Path

# /etc/os-release on Mabox has no distinct ID (ID=manjaro) -- match on NAME instead.
OS_RELEASE_FILE = Path("/etc/os-release")
OS_RELEASE_NAME_MARKER = "Mabox"

SYSTEM_CONFIG_FILE = Path("/etc/mabox-snapshot/mabox-snapshot.conf")
USER_CONFIG_FILE = Path("~/.config/mabox-snapshot/mabox-snapshot.conf").expanduser()
EXCLUDES_LIST_FILE = Path("/etc/mabox-snapshot/excludes.list")
EXCLUDES_LIST_DEFAULT = Path("/usr/share/mabox-snapshot/excludes.list.default")

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

# Deliberately different from the plaintext "rootfs.sfs" name so the boot
# hook can unambiguously tell, from the filename alone, which case it's in.
LUKS_CONTAINER_SUFFIX = ".luks"

# dm-crypt mapper name -- used only transiently during the build (luks.py
# opens then closes it; never left attached) and hardcoded identically in
# configs/initcpio/hooks/miso_luks's _mnt_luks_sfs() for the boot-time
# open. The two never share a process, so this constant is a single
# source of truth to keep the shell copy in sync with, not a runtime link.
ISO_LUKS_MAPPER_NAME = "mabox_rootfs"

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
