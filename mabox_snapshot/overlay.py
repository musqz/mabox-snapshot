"""The central architectural decision: mksquashfs accepts multiple source
directories in one invocation, later sources overriding earlier ones for
identical paths. Preserving mode squashes '/' directly. Reset mode
squashes '/' (with /home and account files excluded) plus a small
purpose-built overlay directory holding only the sanitized replacements
and the synthetic demo account -- never a full-filesystem staging copy,
never overlayfs/bind-mount tricks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import excludes, permissions, sanitize, seed


@dataclass
class BuildPlan:
    mode: str
    sources: list[Path]
    exclude_patterns: list[str]
    overlay_dir: Path | None  # None in preserving mode


def resolve_plan(
    mode: str,
    workdir: Path,
    exclude_list_path: Path,
    exclude_folders: tuple[str, ...] = (),
) -> BuildPlan:
    if mode not in ("preserving", "reset"):
        raise ValueError(f"unknown mode: {mode!r}")

    patterns = excludes.resolve_excludes(mode, exclude_list_path, exclude_folders)

    if mode == "preserving":
        return BuildPlan(mode=mode, sources=[Path("/")], exclude_patterns=patterns, overlay_dir=None)

    overlay_dir = workdir / "overlay"
    return BuildPlan(
        mode=mode,
        sources=[Path("/"), overlay_dir],
        exclude_patterns=patterns,
        overlay_dir=overlay_dir,
    )


def build_overlay(plan: BuildPlan) -> None:
    """Populates plan.overlay_dir for reset mode: the seeded demo home,
    umask-normalized, then the sanitized passwd/shadow/group/etc written
    last (each self-chmod'd -- see sanitize.py -- so write order relative
    to normalize() doesn't matter for their permissions)."""
    if plan.mode != "reset":
        return
    seed.seed_demo_home(plan.overlay_dir)
    permissions.normalize(plan.overlay_dir)
    sanitize.write_sanitized_files(plan.overlay_dir)
