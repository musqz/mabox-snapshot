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

DEFAULT_WORKDIR = Path("/var/lib/mabox-snapshot/work")

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

# Reset-mode-only: files replaced with sanitized versions in the overlay, or
# excluded outright. Paths are relative to '/', matching mksquashfs -ef.
RESET_MODE_REPLACED_FILES = [
    "etc/passwd",
    "etc/shadow",
    "etc/gshadow",
    "etc/group",
    "etc/subuid",
    "etc/subgid",
]
RESET_MODE_ONLY_EXCLUDES = [
    "home/*",
    "etc/machine-id",
    "etc/NetworkManager/system-connections/*",
]

DEMO_USERNAME = "demo"
DEMO_UID = 1000
DEMO_GID = 1000
DEMO_BASELINE_GROUPS = ["wheel", "audio", "video", "storage", "optical", "network"]

REQUIRED_TOOLS = ["mksquashfs", "xorriso", "grub-mkimage", "mkinitcpio", "mkfs.fat", "rsync", "openssl"]
OPTIONAL_TOOLS = ["calamares", "yay", "magick"]

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
