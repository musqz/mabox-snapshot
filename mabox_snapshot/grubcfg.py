"""grub.cfg generation for the live ISO's boot menu.

Not copied from anywhere -- Manjaro's own themed grub.cfg templates ship
only as part of an ISO-build profile (verified: not present on a regular
installed system, only /usr/share/grub's fonts and a background image
are). Generated directly instead: plain text, one menu entry per selected
kernel, booting straight from the ISO9660 filesystem via the miso hook
(misobasedir=/misolabel= on the kernel cmdline -- see constants.py).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import constants

# GRUB draws a background at whatever native size the image is -- a source
# photo with the wrong aspect ratio just looks stretched/cropped oddly.
# Normalizing every splash to one fixed canvas means it looks right
# regardless of what the user dropped in the images folder. The photo is
# shrunk to fit an inner box and padded out to the full canvas with a
# solid border (see build_splash_command()) rather than cropped-to-fill,
# so GRUB's boot menu text -- drawn over the top -- stays readable against
# a flat, dark edge instead of whatever busy detail happened to land at
# the photo's own edges. `magick`, never `convert` (deprecated since
# IMv7).
SPLASH_SIZE = "1920x1080"

# Border thickness as a fraction of the canvas's shorter side, so it
# scales sensibly regardless of SPLASH_SIZE's aspect ratio. Overridable
# per-machine via SnapshotConfig.splash_border_fraction.
DEFAULT_BORDER_FRACTION = 0.06

# Matches magick's `-unique-colors txt:-` hex column (#RRGGBB, optionally
# with a trailing alpha byte on images that have one) -- captures just the
# RGB portion.
_PALETTE_HEX_RE = re.compile(r"#([0-9A-Fa-f]{6})(?:[0-9A-Fa-f]{2})?\b")


def extract_palette(source: Path, n_colors: int = 8) -> list[tuple[int, int, int]]:
    """Quantizes source down to n_colors dominant colors, for
    darkest_color() to pick a border color from. Downsampled to 100x100
    first -- quantization only cares about the color distribution, not
    resolution, and this keeps it fast even against a large source photo.
    Execution-layer (runs real magick), not unit-tested -- same untested-
    execution-layer precedent as normalize_splash() below."""
    result = subprocess.run(
        ["magick", str(source), "-resize", "100x100", "+dither", "-colors", str(n_colors), "-unique-colors", "txt:-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)) for h in _PALETTE_HEX_RE.findall(result.stdout)]


def darkest_color(palette: list[tuple[int, int, int]]) -> str:
    """Picks the perceptually-darkest color from a palette (e.g. from
    extract_palette()) and returns it as a '#RRGGBB' magick-compatible
    hex string. Luma-weighted (ITU-R BT.601), not a flat RGB sum, so a
    saturated dark blue reads as darker than a similarly-bright gray --
    matching how the color actually looks to a viewer, which is what
    matters for text legibility against it."""
    if not palette:
        raise ValueError("palette must contain at least one color")
    r, g, b = min(palette, key=lambda rgb: 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2])
    return f"#{r:02X}{g:02X}{b:02X}"


def border_px(size: str = SPLASH_SIZE, fraction: float = DEFAULT_BORDER_FRACTION) -> int:
    width, height = (int(v) for v in size.split("x"))
    return round(min(width, height) * fraction)


def build_splash_command(
    source: Path,
    dest: Path,
    border_color: str,
    size: str = SPLASH_SIZE,
    fraction: float = DEFAULT_BORDER_FRACTION,
) -> list[str]:
    width, height = (int(v) for v in size.split("x"))
    px = border_px(size, fraction)
    inner = f"{width - 2 * px}x{height - 2 * px}"
    return [
        "magick",
        str(source),
        "-resize",
        f"{inner}^",
        "-gravity",
        "center",
        "-extent",
        inner,
        "-bordercolor",
        border_color,
        "-border",
        str(px),
        str(dest),
    ]


def normalize_splash(
    source: Path,
    dest: Path,
    border_color: str,
    size: str = SPLASH_SIZE,
    fraction: float = DEFAULT_BORDER_FRACTION,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_splash_command(source, dest, border_color, size, fraction), check=True)


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
        "terminal_output gfxterm",
    ]
    if has_splash:
        lines += ["insmod png", "background_image /boot/grub/splash.png"]
    lines.append("")
    lines += [_menu_entry(name, misolabel) for name in kernel_names]
    return "\n".join(lines) + "\n"
