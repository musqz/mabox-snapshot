"""The central architectural decision: each build produces one or more
INDEPENDENT, single-source squashfs layers, never a single mksquashfs
invocation given multiple source directories. That multi-source form was
the original design here, but mksquashfs's -ef exclude patterns silently
stop matching anything once given more than one source (verified
empirically -- a real, since-fixed bug: reset-mode builds were shipping
the full, unsanitized live system, home directory included, with every
exclude pattern silently inert). Single-source excludes work correctly,
so preserving mode squashes '/' alone into one "rootfs" layer, and reset
mode squashes '/' (with /home and account files excluded) and the small
sanitized overlay directory into TWO separate layers ("rootfs" and
"desktopfs"). They are never merged at build time -- they merge at BOOT
time instead, via the existing miso initramfs hook's own overlayfs
layering (livefs/mhwdfs/desktopfs/rootfs, already unmodified stock
behaviour -- "desktopfs" was already one of its four recognized layer
names, so reset mode needs no boot-side changes at all to pick this up).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import calamares, constants, excludes, permissions, sanitize, seed


@dataclass
class BuildLayer:
    name: str  # "rootfs" or "desktopfs" -- must be a name the miso hook recognizes
    source: Path
    exclude_patterns: list[str]


@dataclass
class BuildPlan:
    mode: str
    layers: list[BuildLayer]
    overlay_dir: Path | None  # None in preserving mode


def _self_exclude_patterns(*dirs: Path) -> list[str]:
    """The rootfs layer's source is '/' itself, so without this, mksquashfs
    would recurse into the tool's own workdir/output-dir -- including the
    very .sfs file it's writing, mid-write, growing every time it's
    re-read (this is what actually drove at least one real multi-hundred-
    GB runaway build, previously misattributed entirely to the exclude-
    pattern bug this module's docstring describes). Paths are relative to
    '/', matching mksquashfs -ef; dedup by rendered pattern since workdir
    and output_dir are often the same directory."""
    rendered = []
    for d in dirs:
        pattern = f"{d.relative_to('/')}/*"
        if pattern not in rendered:
            rendered.append(pattern)
    return rendered


def resolve_plan(
    mode: str,
    workdir: Path,
    exclude_list_path: Path,
    exclude_folders: tuple[str, ...] = (),
    output_dir: Path | None = None,
    mounts_file: Path | None = None,
    override_rules_path: Path | None = None,
    override_root: Path | None = None,
) -> BuildPlan:
    if mode not in ("preserving", "reset"):
        raise ValueError(f"unknown mode: {mode!r}")

    patterns = excludes.resolve_excludes(
        mode,
        exclude_list_path,
        exclude_folders,
        override_rules_path=override_rules_path or constants.OVERRIDE_RULES_FILE,
        override_root=override_root or Path("/"),
    )
    patterns += _self_exclude_patterns(workdir, output_dir or workdir)
    patterns += excludes.detect_foreign_mount_excludes(mounts=mounts_file or constants.MOUNTS_FILE)
    patterns = list(dict.fromkeys(patterns))  # dedup across the three sources above, keep order
    rootfs_layer = BuildLayer(name="rootfs", source=Path("/"), exclude_patterns=patterns)

    if mode == "preserving":
        return BuildPlan(mode=mode, layers=[rootfs_layer], overlay_dir=None)

    overlay_dir = workdir / "overlay"
    # No excludes needed here: this directory only ever contains what
    # seed.py/sanitize.py/calamares.py themselves wrote, nothing to filter.
    desktop_layer = BuildLayer(name="desktopfs", source=overlay_dir, exclude_patterns=[])
    return BuildPlan(mode=mode, layers=[rootfs_layer, desktop_layer], overlay_dir=overlay_dir)


def build_overlay(plan: BuildPlan) -> None:
    """Populates plan.overlay_dir for reset mode: the seeded demo home,
    the same skel tree seeded to etc/skel/ (so an account created later
    -- Calamares' users job during install, or a plain useradd -- gets
    Mabox's own desktop too, not the rootfs layer's bare stock skel; see
    seed.seed_etc_skel()), Mabox's own Calamares branding, and --
    unconditionally, independent of branding -- the removeuser override
    that strips reset mode's demo account back out during install (see
    calamares.py's insert_removeuser_job()). Then umask-normalized, then
    the sanitized passwd/shadow/group/etc written last (each
    self-chmod'd -- see sanitize.py -- so write order relative to
    normalize() doesn't matter for their permissions)."""
    if plan.mode != "reset":
        return
    seed.seed_demo_home(plan.overlay_dir)
    seed.seed_etc_skel(plan.overlay_dir)
    calamares.write_branding(plan.overlay_dir)
    calamares.write_settings_override(plan.overlay_dir)
    calamares.write_removeuser_override(plan.overlay_dir)
    permissions.normalize(plan.overlay_dir)
    sanitize.write_sanitized_files(plan.overlay_dir)
