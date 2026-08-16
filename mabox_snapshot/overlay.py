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

from . import excludes


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
    """Populates plan.overlay_dir for reset mode: sanitized passwd/shadow/
    group/etc plus the seeded demo account home. Not implemented yet --
    lands with sanitize.py/seed.py."""
    if plan.mode != "reset":
        return
    raise NotImplementedError("reset-mode overlay population lands with sanitize.py/seed.py")
