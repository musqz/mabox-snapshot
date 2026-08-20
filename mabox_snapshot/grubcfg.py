"""grub.cfg generation for the live ISO's boot menu.

Not copied from anywhere -- Manjaro's own themed grub.cfg templates ship
only as part of an ISO-build profile (verified: not present on a regular
installed system, only /usr/share/grub's fonts and a background image
are). Generated directly instead: plain text, one menu entry per selected
kernel, booting straight from the ISO9660 filesystem via the miso hook
(misobasedir=/misolabel= on the kernel cmdline -- see constants.py).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import constants

# GRUB draws a background at whatever native size the image is -- a source
# photo with the wrong aspect ratio just looks stretched/cropped oddly.
# Normalizing every splash to one fixed canvas means it looks right
# regardless of what the user dropped in the images folder. Cropped to
# fill edge-to-edge (no shrinking, no padding) rather than letterboxed, so
# the photo stays fully visible with no bars. `magick`, never `convert`
# (deprecated since IMv7).
SPLASH_SIZE = "1920x1080"


def build_splash_command(source: Path, dest: Path, size: str = SPLASH_SIZE) -> list[str]:
    return ["magick", str(source), "-resize", f"{size}^", "-gravity", "center", "-extent", size, str(dest)]


def normalize_splash(source: Path, dest: Path, size: str = SPLASH_SIZE) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_splash_command(source, dest, size), check=True)


def _menu_entry(kernel_name: str, misolabel: str) -> str:
    return (
        f'menuentry "Mabox Linux (live) -- {kernel_name}" {{\n'
        f"    linux /boot/vmlinuz-{kernel_name} "
        f"misobasedir={constants.MISO_BASEDIR} misolabel={misolabel} quiet\n"
        f"    initrd /boot/initramfs-{kernel_name}.img\n"
        f"}}\n"
    )


def build_grub_cfg(kernel_names: list[str], misolabel: str = constants.ISO_VOLID, has_splash: bool = False) -> str:
    if not kernel_names:
        raise ValueError("at least one kernel is required to generate a boot menu")

    lines = [
        "set default=0",
        "set timeout=5",
        "insmod all_video",
        "insmod gfxterm",
        "insmod font",
        "loadfont /boot/grub/unicode.pf2",
        "terminal_output gfxterm",
    ]
    if has_splash:
        lines += ["insmod png", "background_image /boot/grub/splash.png"]
    lines.append("")
    lines += [_menu_entry(name, misolabel) for name in kernel_names]
    return "\n".join(lines) + "\n"
