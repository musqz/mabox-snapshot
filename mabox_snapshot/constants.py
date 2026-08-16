"""Every hardcoded Mabox/Manjaro filesystem path, in one place."""

from pathlib import Path

# /etc/os-release on Mabox has no distinct ID (ID=manjaro) -- match on NAME instead.
OS_RELEASE_FILE = Path("/etc/os-release")
OS_RELEASE_NAME_MARKER = "Mabox"

SYSTEM_CONFIG_FILE = Path("/etc/mabox-snapshot/mabox-snapshot.conf")
USER_CONFIG_FILE = Path("~/.config/mabox-snapshot/mabox-snapshot.conf").expanduser()
EXCLUDES_LIST_FILE = Path("/etc/mabox-snapshot/excludes.list")

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

REQUIRED_TOOLS = ["mksquashfs", "xorriso", "grub-mkimage", "rsync", "openssl"]
OPTIONAL_TOOLS = ["calamares", "yay"]

SUPPORTED_DEMO_LANGS = ["en", "es", "pl"]
DEFAULT_DEMO_LANG = "en"
