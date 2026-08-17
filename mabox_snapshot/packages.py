"""Package-list capture. Explicit repo packages are trivially reproducible
on a fresh install; foreign/manually-installed packages (AUR via yay/paru,
or hand-built .pkg.tar.zst) are where mx-snapshot itself gives up -- here
they're cross-checked against the AUR so the reproducible ones can
actually be reinstalled, not just flagged as unreproducible.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import constants


def explicit_packages() -> list[str]:
    """pacman -Qqe -- explicitly installed, repo-resolvable packages."""
    result = subprocess.run(["pacman", "-Qqe"], capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


def foreign_packages() -> list[str]:
    """pacman -Qqm -- installed but not in any sync db (AUR or hand-built)."""
    result = subprocess.run(["pacman", "-Qqm"], capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


@dataclass
class ForeignPackageReport:
    aur_reproducible: list[str]
    local_only: list[str]


def _default_aur_check(pkg: str) -> bool:
    result = subprocess.run(["yay", "-Si", pkg], capture_output=True, text=True)
    return result.returncode == 0


def split_foreign_packages(packages: list[str], is_aur_available=_default_aur_check) -> ForeignPackageReport:
    """Cross-check each foreign package against the AUR. `is_aur_available`
    is injectable so this is testable without a real yay/network call."""
    if not packages:
        return ForeignPackageReport(aur_reproducible=[], local_only=[])
    if is_aur_available is _default_aur_check and not shutil.which("yay"):
        raise RuntimeError("yay not found -- required to check AUR reproducibility")

    aur, local = [], []
    for pkg in packages:
        (aur if is_aur_available(pkg) else local).append(pkg)
    return ForeignPackageReport(aur_reproducible=aur, local_only=local)


def copy_pacman_config(dest_root: Path) -> None:
    """Copy pacman.conf + mirrorlist verbatim into the overlay. No personal
    data in either, safe in both modes -- and necessary so a fresh install
    points at Mabox's own repo + Manjaro's staged mirrors, not vanilla Arch's."""
    for src in (constants.PACMAN_CONF, constants.PACMAN_MIRRORLIST):
        if not src.exists():
            continue
        dest = dest_root / src.relative_to("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
