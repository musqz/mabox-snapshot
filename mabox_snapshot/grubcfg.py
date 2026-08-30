"""grub.cfg generation for the live ISO's boot menu.

Not copied from anywhere -- Manjaro's own themed grub.cfg templates ship
only as part of an ISO-build profile (verified: not present on a regular
installed system, only /usr/share/grub's fonts and a background image
are). Generated directly instead: plain text, one menu entry per selected
kernel, booting straight from the ISO9660 filesystem via the miso hook
(misobasedir=/misolabel= on the kernel cmdline -- see constants.py).

A "safe graphics" entry is always appended: the newest kernel with KMS
disabled (nomodeset), for machines that show a black or garbled screen on
the normal entry. `quiet` is dropped there so a later failure stays
visible. Same rationale as every mainstream distro ISO shipping one.

A "memory test" entry is appended too when the build host has memtest86+
installed. memtest is a standalone image, not a kernel + initramfs: the
BIOS entry loads the raw .bin with `linux16` (as Arch's own
/etc/grub.d/60_memtest86+ does), the UEFI entry chainloads the .efi from
the separate, unsigned memtest86+-efi package (needs Secure Boot disabled).
Each is wrapped in a ${grub_platform} guard so a machine only ever sees
the one that will run on it.
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


def _menu_entry(kernel_name: str, misolabel: str, title: str, params: str) -> str:
    return (
        f'menuentry "{title}" {{\n'
        f"    linux /boot/vmlinuz-{kernel_name} "
        f"misobasedir={constants.MISO_BASEDIR} misolabel={misolabel} {params}\n"
        f"    initrd /boot/initramfs-{kernel_name}.img\n"
        f"}}\n"
    )


def _memtest_blocks(bios: bool, efi: bool) -> list[str]:
    """A ${grub_platform}-guarded memtest86+ entry per available image, so
    a machine only sees the one it can boot. BIOS wants the raw .bin via
    `linux16`; UEFI chainloads the .efi PE binary. No misobasedir/misolabel
    -- memtest is self-contained and never touches the live rootfs."""
    title = "Mabox Linux (live) -- memory test (memtest86+)"
    blocks = []
    if bios:
        blocks.append(
            'if [ "${grub_platform}" = "pc" ]; then\n'
            f'menuentry "{title}" {{\n'
            "    linux16 /boot/memtest86+/memtest.bin\n"
            "}\n"
            "fi\n"
        )
    if efi:
        blocks.append(
            'if [ "${grub_platform}" = "efi" ]; then\n'
            f'menuentry "{title}" {{\n'
            "    chainloader /boot/memtest86+/memtest.efi\n"
            "}\n"
            "fi\n"
        )
    return blocks


def build_grub_cfg(
    kernel_names: list[str],
    misolabel: str = constants.ISO_VOLID,
    has_splash: bool = False,
    memtest_bios: bool = False,
    memtest_efi: bool = False,
) -> str:
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
    lines += [
        _menu_entry(name, misolabel, f"Mabox Linux (live) -- {name}", "quiet")
        for name in kernel_names
    ]
    lines.append(
        _menu_entry(
            kernel_names[0],
            misolabel,
            "Mabox Linux (live) -- safe graphics (nomodeset)",
            "nomodeset",
        )
    )
    lines += _memtest_blocks(memtest_bios, memtest_efi)
    return "\n".join(lines) + "\n"
