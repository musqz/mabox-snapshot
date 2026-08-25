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


def build_command(
    sources: list[Path],
    dest: Path,
    exclude_file: Path | None,
    compression: str,
    compression_level: int | None,
    pseudo_files: list[str] | None = None,
    pseudo_file_list: Path | None = None,
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
    # -pf reads many pseudo-file specs from a file, one per line -- the
    # right tool once there are hundreds of them (see seed.py's
    # etc_skel_pseudo_specs()); individual -p args stay in use above for
    # the handful of small, fixed etc/calamares/* entries, where they're
    # still readable in a printed dry-run command.
    if pseudo_file_list is not None:
        cmd += ["-pf", str(pseudo_file_list)]
    return cmd


def build(
    sources: list[Path],
    dest: Path,
    exclude_file: Path | None = None,
    compression: str = "zstd",
    compression_level: int | None = None,
    pseudo_files: list[str] | None = None,
    pseudo_file_list: Path | None = None,
) -> None:
    cmd = build_command(sources, dest, exclude_file, compression, compression_level, pseudo_files, pseudo_file_list)
    subprocess.run(cmd, check=True)
