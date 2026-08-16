"""Detect installed kernels via their mkinitcpio presets.

Manjaro/Mabox ships versioned, parallel-installable kernel packages
(linux612, linux618, ...) rather than Arch's single rolling `linux`
package -- both can be installed and bootable at once. Detection reads
each preset's ALL_kver/default_image rather than guessing from the
package name, so linux-lts/linux-zen work the same way if present.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MKINITCPIO_PRESET_DIR = Path("/etc/mkinitcpio.d")

_KVER_RE = re.compile(r'^\s*ALL_kver\s*=\s*"([^"]+)"', re.MULTILINE)
_IMAGE_RE = re.compile(r'^\s*default_image\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class KernelInfo:
    name: str  # preset stem, e.g. "linux618" -- also the pacman package name
    preset_path: Path
    vmlinuz: Path
    default_image: Path


def detect_installed_kernels(preset_dir: Path = MKINITCPIO_PRESET_DIR) -> list[KernelInfo]:
    if not preset_dir.exists():
        return []

    kernels = []
    for preset_path in sorted(preset_dir.glob("*.preset")):
        text = preset_path.read_text()
        kver_match = _KVER_RE.search(text)
        image_match = _IMAGE_RE.search(text)
        if not kver_match or not image_match:
            continue

        vmlinuz = Path(kver_match.group(1))
        if not vmlinuz.exists():
            continue  # stale preset left behind by a removed kernel

        kernels.append(
            KernelInfo(
                name=preset_path.stem,
                preset_path=preset_path,
                vmlinuz=vmlinuz,
                default_image=Path(image_match.group(1)),
            )
        )
    return kernels


def find_kernel(name: str, preset_dir: Path = MKINITCPIO_PRESET_DIR) -> KernelInfo | None:
    for kernel in detect_installed_kernels(preset_dir):
        if kernel.name == name:
            return kernel
    return None
