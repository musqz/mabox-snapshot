"""Detect installed kernels via their mkinitcpio presets.

Manjaro/Mabox ships versioned, parallel-installable kernel packages
(linux612, linux618, ...) rather than Arch's single rolling `linux`
package -- both can be installed and bootable at once. Detection reads
each preset's ALL_kver/default_image rather than guessing from the
package name, so linux-lts/linux-zen work the same way if present.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MKINITCPIO_PRESET_DIR = Path("/etc/mkinitcpio.d")

_KVER_RE = re.compile(r'^\s*ALL_kver\s*=\s*"([^"]+)"', re.MULTILINE)
_IMAGE_RE = re.compile(r'^\s*default_image\s*=\s*"([^"]+)"', re.MULTILINE)
_MODULES_DIR_RE = re.compile(r"/usr/lib/modules/([^/\s]+)/$")


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


def _default_pacman_ql(package: str) -> str:
    result = subprocess.run(["pacman", "-Ql", package], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def module_version(kernel: KernelInfo, query=_default_pacman_ql) -> str | None:
    """Correlates a kernel preset to its /usr/lib/modules/<version>/ dir via
    `pacman -Ql <package>` (verified: package name matches preset name --
    linux618 owns /usr/lib/modules/6.18.44-1-MANJARO/). mkinitcpio -k needs
    this exact version string; the preset's own ALL_kver is a vmlinuz path,
    not a version. `query` is injectable so this is testable without pacman."""
    for line in query(kernel.name).splitlines():
        match = _MODULES_DIR_RE.search(line.strip())
        if match:
            return match.group(1)
    return None
