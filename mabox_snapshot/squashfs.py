"""mksquashfs wrapper.

mksquashfs's own CLI requires sources+dest before any options (verified
on this host: `mksquashfs -help` alone errors with exactly that rule) --
build_command() follows that order.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SUPPORTED_COMPRESSORS = ["zstd", "xz", "lz4", "lzo", "gzip"]


def _parse_compressors(help_text: str) -> list[str]:
    match = re.search(r"Compressors available:\s*((?:\s+\S+\n?)+)", help_text)
    if not match:
        return []
    listed = {line.strip().split()[0] for line in match.group(1).splitlines() if line.strip()}
    return [c for c in SUPPORTED_COMPRESSORS if c in listed]


def available_compressors() -> list[str]:
    """Probe `mksquashfs -help-section compression` for which compressors
    this host's build actually supports, rather than assuming all of them
    are compiled in."""
    result = subprocess.run(
        ["mksquashfs", "-help-section", "compression"], capture_output=True, text=True
    )
    return _parse_compressors(result.stdout + result.stderr)


def build_command(
    sources: list[Path],
    dest: Path,
    exclude_file: Path | None,
    compression: str,
    compression_level: int | None,
    pseudo_files: list[str] | None = None,
) -> list[str]:
    cmd = [
        "mksquashfs",
        *[str(s) for s in sources],
        str(dest),
        "-noappend",
        "-comp",
        compression,
    ]
    if exclude_file is not None:
        cmd += ["-wildcards", "-ef", str(exclude_file)]
    if compression_level is not None:
        cmd += ["-Xcompression-level", str(compression_level)]
    for spec in pseudo_files or []:
        cmd += ["-p", spec]
    return cmd


def build(
    sources: list[Path],
    dest: Path,
    exclude_file: Path | None = None,
    compression: str = "zstd",
    compression_level: int | None = None,
    pseudo_files: list[str] | None = None,
) -> None:
    cmd = build_command(sources, dest, exclude_file, compression, compression_level, pseudo_files)
    subprocess.run(cmd, check=True)
