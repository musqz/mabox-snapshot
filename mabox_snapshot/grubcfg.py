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
# regardless of what the user dropped in the images folder. `magick`,
# never `convert` (deprecated since IMv7).
SPLASH_SIZE = "1920x1080"

# A hard geometric border (an earlier version of this: shrink the photo,
# pad out with a solid color) can't reliably guarantee GRUB's own UI text
# -- the menu list at the top, "press e to edit"-style help text at the
# bottom -- actually lands on it: the menu's height depends on how many
# kernels this build includes, and GRUB's real graphics resolution (and
# therefore its font/row size relative to our fixed-size canvas) varies
# by hardware. Confirmed against a real VM boot: with a 6%-of-shorter-
# side border, both the menu list and the help text sat on the busy photo
# instead. A dark top/bottom fade instead of a hard edge guarantees good
# contrast wherever that text actually renders, without needing to know
# GRUB's exact row geometry -- and the photo stays fully visible,
# edge-to-edge, everywhere the fade doesn't reach. Height of that fade, at
# both the top and bottom, as a fraction of SPLASH_SIZE's height.
# Overridable per-machine via SnapshotConfig.splash_overlay_fraction.
DEFAULT_OVERLAY_FRACTION = 0.18

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


def overlay_height_px(size: str = SPLASH_SIZE, fraction: float = DEFAULT_OVERLAY_FRACTION) -> int:
    _, height = (int(v) for v in size.split("x"))
    return round(height * fraction)


def build_splash_command(
    source: Path,
    dest: Path,
    overlay_color: str,
    size: str = SPLASH_SIZE,
    fraction: float = DEFAULT_OVERLAY_FRACTION,
) -> list[str]:
    """Crops the photo to fill the full canvas edge-to-edge (no shrinking,
    no padding), then composites a top-to-transparent gradient at the top
    and a transparent-to-bottom gradient at the bottom -- solid-ish right
    at the edges, fading into the untouched photo toward the middle. Both
    gradients are drawn via magick's `gradient:` pseudo-format ('none' is
    its documented fully-transparent stop), composited with -gravity
    north/south so they land exactly at the canvas edges regardless of
    overlay_height_px()'s size."""
    width, height = (int(v) for v in size.split("x"))
    band = f"{width}x{overlay_height_px(size, fraction)}"
    return [
        "magick",
        str(source),
        "-resize",
        f"{size}^",
        "-gravity",
        "center",
        "-extent",
        size,
        "(",
        "-size",
        band,
        f"gradient:{overlay_color}-none",
        ")",
        "-gravity",
        "north",
        "-composite",
        "(",
        "-size",
        band,
        f"gradient:none-{overlay_color}",
        ")",
        "-gravity",
        "south",
        "-composite",
        str(dest),
    ]


def normalize_splash(
    source: Path,
    dest: Path,
    overlay_color: str,
    size: str = SPLASH_SIZE,
    fraction: float = DEFAULT_OVERLAY_FRACTION,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_splash_command(source, dest, overlay_color, size, fraction), check=True)


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
