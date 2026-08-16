"""grub.cfg generation for the live ISO's boot menu.

Not copied from anywhere -- Manjaro's own themed grub.cfg templates ship
only as part of an ISO-build profile (verified: not present on a regular
installed system, only /usr/share/grub's fonts and a background image
are). Generated directly instead: plain text, one menu entry per selected
kernel, booting straight from the ISO9660 filesystem via the miso hook
(misobasedir=/misolabel= on the kernel cmdline -- see constants.py).
"""

from __future__ import annotations

from . import constants


def _menu_entry(kernel_name: str, misolabel: str) -> str:
    return (
        f'menuentry "Mabox Linux (live) -- {kernel_name}" {{\n'
        f"    linux /boot/vmlinuz-{kernel_name} "
        f"misobasedir={constants.MISO_BASEDIR} misolabel={misolabel} quiet\n"
        f"    initrd /boot/initramfs-{kernel_name}.img\n"
        f"}}\n"
    )


def build_grub_cfg(kernel_names: list[str], misolabel: str = constants.ISO_VOLID) -> str:
    if not kernel_names:
        raise ValueError("at least one kernel is required to generate a boot menu")

    lines = [
        "set default=0",
        "set timeout=5",
        "insmod all_video",
        "insmod gfxterm",
        "terminal_output gfxterm",
        "",
    ]
    lines += [_menu_entry(name, misolabel) for name in kernel_names]
    return "\n".join(lines) + "\n"
