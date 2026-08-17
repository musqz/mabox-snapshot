"""argparse dispatch for the mabox-snapshot CLI."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from . import calamares, changes, config, constants, excludes, grubcfg, history, isobuild, kernels, overlay, packages, permissions, privilege, retention, squashfs
from . import workdir as workdir_mod
from . import __version__


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"mabox-snapshot {__version__}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    ok = True

    os_release = constants.OS_RELEASE_FILE.read_text() if constants.OS_RELEASE_FILE.exists() else ""
    if constants.OS_RELEASE_NAME_MARKER in os_release:
        print(f"[ok]   {constants.OS_RELEASE_FILE} identifies as Mabox")
    else:
        print(f"[fail] {constants.OS_RELEASE_FILE} does not look like Mabox Linux")
        ok = False

    for tool in constants.REQUIRED_TOOLS:
        if shutil.which(tool):
            print(f"[ok]   {tool} found")
        else:
            print(f"[fail] {tool} not found")
            ok = False

    for tool in constants.OPTIONAL_TOOLS:
        if shutil.which(tool):
            print(f"[ok]   {tool} found (optional)")
        else:
            print(f"[warn] {tool} not found (optional)")

    usage = shutil.disk_usage(constants.DEFAULT_WORKDIR.parent if constants.DEFAULT_WORKDIR.parent.exists() else "/")
    free_gib = usage.free / (1024**3)
    print(f"[info] {free_gib:.1f} GiB free at {constants.DEFAULT_WORKDIR.parent}")

    detected = kernels.detect_installed_kernels()
    if detected:
        print(f"[info] {len(detected)} kernel(s) detected: {', '.join(k.name for k in detected)}")
    else:
        print("[warn] no installed kernels detected via mkinitcpio presets")

    return 0 if ok else 1


def _apply_create_overrides(cfg: config.SnapshotConfig, args: argparse.Namespace) -> config.SnapshotConfig:
    overrides = {}
    if args.workdir is not None:
        overrides["workdir"] = args.workdir
    if args.output_dir is not None:
        overrides["output_dir"] = args.output_dir
    if args.compression is not None:
        overrides["compression"] = args.compression
    if args.compression_level is not None:
        overrides["compression_level"] = args.compression_level
    if args.exclude_list is not None:
        overrides["exclude_list"] = args.exclude_list
    if args.exclude_folder:
        overrides["exclude_folders"] = tuple(args.exclude_folder)
    if args.kernel is not None:
        overrides["kernel"] = args.kernel
    if args.all_kernels:
        overrides["all_kernels"] = True
    if args.skip_space_check:
        overrides["skip_space_check"] = True
    if args.keep_workdir:
        overrides["keep_workdir"] = True
    if args.month:
        overrides["month"] = True
    if args.max_age_days is not None:
        overrides["max_age_days"] = args.max_age_days
    if args.change_threshold_mb is not None:
        overrides["change_threshold_mb"] = args.change_threshold_mb
    return replace(cfg, **overrides)


def cmd_create(args: argparse.Namespace) -> int:
    cfg = _apply_create_overrides(config.load(), args)

    plan = overlay.resolve_plan(args.mode, cfg.workdir, cfg.exclude_list, cfg.exclude_folders)

    detected = kernels.detect_installed_kernels()
    if not detected:
        print("error: no installed kernel detected (checked /etc/mkinitcpio.d/*.preset)", file=sys.stderr)
        return 1
    if cfg.all_kernels:
        selected = detected
    elif cfg.kernel:
        match = kernels.find_kernel(cfg.kernel)
        if match is None:
            names = ", ".join(k.name for k in detected)
            print(f"error: kernel {cfg.kernel!r} not found (installed: {names})", file=sys.stderr)
            return 1
        selected = [match]
    else:
        selected = detected[-1:]  # newest-sorted preset by default; --kernel/--all-kernels overrides

    kvers = {}
    for k in selected:
        kver = kernels.module_version(k)
        if kver is None:
            print(f"error: could not resolve {k.name!r} to a /usr/lib/modules/<version> (pacman -Ql {k.name})", file=sys.stderr)
            return 1
        kvers[k.name] = kver

    output_dir = cfg.output_dir or cfg.workdir
    stamp = datetime.now().strftime("%Y-%m" if cfg.month else "%Y-%m-%d-%H%M")
    iso_name = args.iso_name or f"{constants.ISO_NAME_PREFIX}{args.mode}-{stamp}"
    dest = output_dir / f"{iso_name}.iso"

    iso_root = cfg.workdir / "iso"
    sfs_dest = iso_root / constants.MISO_BASEDIR / constants.ISO_ARCH / "rootfs.sfs"
    mkinitcpio_conf = cfg.workdir / "mkinitcpio-miso.conf"
    exclude_file = cfg.workdir / "exclude.list" if plan.exclude_patterns else None

    splash_source = constants.IMAGES_DIR / "splash.png"
    has_splash = splash_source.exists()
    splash_dest = iso_root / "boot" / "grub" / "splash.png"

    branding = calamares.load_branding() if args.mode == "reset" else None

    sfs_cmd = squashfs.build_command(plan.sources, sfs_dest, exclude_file, cfg.compression, cfg.compression_level)
    initramfs_cmds = [
        isobuild.build_mkinitcpio_command(
            kvers[k.name], mkinitcpio_conf, iso_root / "boot" / f"initramfs-{k.name}.img"
        )
        for k in selected
    ]
    bios_cmd = isobuild.build_bios_boot_command(iso_root / "boot" / "grub" / "i386-pc")
    efi_cmd = isobuild.build_efi_boot_command(
        cfg.workdir / "grub-x86_64-efi", iso_root / "efi" / "boot" / "bootx64.efi"
    )
    xorriso_cmd = isobuild.build_xorriso_command(iso_root, dest, constants.ISO_VOLID)

    print(f"mode:        {plan.mode}")
    print(f"sources:     {', '.join(str(s) for s in plan.sources)}")
    print(f"excludes:    {len(plan.exclude_patterns)} pattern(s)")
    print(f"kernels:     {', '.join(f'{k.name} ({kvers[k.name]})' for k in selected)}")
    level = f" (level {cfg.compression_level})" if cfg.compression_level is not None else ""
    print(f"compression: {cfg.compression}{level}")
    print(f"workdir:     {cfg.workdir}")
    print(f"output:      {dest}")
    print(f"squashfs:    {' '.join(str(c) for c in sfs_cmd)}")
    for cmd in initramfs_cmds:
        print(f"initramfs:   {' '.join(str(c) for c in cmd)}")
    if has_splash:
        print(f"splash:      {' '.join(str(c) for c in grubcfg.build_splash_command(splash_source, splash_dest))}")
    else:
        print(f"splash:      none configured ({splash_source} not found) -- plain grub boot menu")
    if args.mode == "reset":
        note = f"{len(branding.slides)} slide(s) from {constants.IMAGES_DIR}" if branding else "none configured -- stock Manjaro branding"
        print(f"calamares:   {note}")
    print(f"bios boot:   {' '.join(str(c) for c in bios_cmd)}")
    print(f"efi boot:    {' '.join(str(c) for c in efi_cmd)}")
    print(f"assemble:    {' '.join(str(c) for c in xorriso_cmd)}")

    if args.dry_run:
        return 0

    try:
        privilege.require_root("mabox-snapshot create")
    except privilege.NotRootError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    workdir_mod.ensure_workdir(cfg.workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sfs_dest.parent.mkdir(parents=True, exist_ok=True)

    # No staging copy exists to size precisely (mksquashfs reads live '/' directly).
    # The final ISO embeds the same bytes again (ISO9660 is a monolithic image, not
    # a reference format), so budget one squashfs_estimate share for the squashfs
    # itself (always staged under workdir) and another for the ISO (written to
    # output_dir, which defaults to workdir but may be a separate --output-dir
    # mount -- e.g. an external drive -- in which case it needs its own check).
    squashfs_estimate = int(shutil.disk_usage("/").used * 0.5)
    workdir_required = squashfs_estimate if output_dir != cfg.workdir else squashfs_estimate * 2
    try:
        workdir_mod.check_free_space(cfg.workdir, workdir_required, skip=cfg.skip_space_check)
        if output_dir != cfg.workdir:
            workdir_mod.check_free_space(output_dir, squashfs_estimate, skip=cfg.skip_space_check)
    except workdir_mod.InsufficientSpaceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Best-effort: compares this run's home-dir scan against the last stored
    # manifest and, interactively, offers to exclude anything new/grown past
    # cfg.change_threshold_mb (see changes.py). A failure here (no SUDO_USER,
    # no prior history yet) must never block the build -- current_entries
    # stays None and write_manifest() below falls back to scanning itself.
    current_entries = None
    try:
        home = privilege.resolve_home_dir()
        current_entries = history.scan_home_entries(home)
        previous = history.latest(1)
        if previous:
            threshold_bytes = cfg.change_threshold_mb * 1024 * 1024
            changed = changes.diff_entries(previous[0].entries, current_entries, threshold_bytes)
            new_excludes = changes.prompt_for_exclusions(changed, home)
            if new_excludes:
                plan.exclude_patterns.extend(new_excludes)
                if exclude_file is None:
                    exclude_file = cfg.workdir / "exclude.list"
    except Exception as e:
        print(f"warning: change notification skipped: {e}", file=sys.stderr)

    try:
        overlay.build_overlay(plan)  # no-op for preserving mode
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if exclude_file is not None:
        excludes.write_mksquashfs_exclude_file(plan.exclude_patterns, exclude_file)
    squashfs.build(plan.sources, sfs_dest, exclude_file, cfg.compression, cfg.compression_level)

    (iso_root / "boot").mkdir(parents=True, exist_ok=True)
    isobuild.write_mkinitcpio_conf(mkinitcpio_conf)
    for k in selected:
        shutil.copy2(k.vmlinuz, iso_root / "boot" / f"vmlinuz-{k.name}")
        isobuild.build_initramfs(kvers[k.name], mkinitcpio_conf, iso_root / "boot" / f"initramfs-{k.name}.img")

    if has_splash:
        grubcfg.normalize_splash(splash_source, splash_dest)

    grub_cfg_dest = iso_root / "boot" / "grub" / "grub.cfg"
    grub_cfg_dest.parent.mkdir(parents=True, exist_ok=True)
    # detect_installed_kernels() sorts oldest-first; reverse so grub's default
    # entry (index 0, see grubcfg.build_grub_cfg) boots the newest kernel.
    menu_kernel_names = [k.name for k in reversed(selected)]
    grub_cfg_dest.write_text(grubcfg.build_grub_cfg(menu_kernel_names, constants.ISO_VOLID, has_splash=has_splash))

    isobuild.prepare_bios_boot(iso_root)
    isobuild.prepare_efi_boot(iso_root, cfg.workdir)
    isobuild.assemble(iso_root, dest, constants.ISO_VOLID)
    # Not cfg.workdir as a whole: the overlay dir (reset mode) already had its
    # own normalize() + sanitize pass inside build_overlay(), which explicitly
    # chmods shadow/gshadow 0640 -- a blanket re-normalize here would widen
    # them back to world-readable.
    permissions.normalize(iso_root)

    print(f"ISO written to {dest}")

    # Best-effort only: the ISO is already written and is the primary
    # deliverable, so a manifest failure (e.g. /var/lib full/unwritable, or
    # SUDO_USER unset) must warn, not abort -- deliberately not the usual
    # try/except + print error + return 1 idiom used above.
    try:
        history.write_manifest(dest, args.mode, entries=current_entries)
    except Exception as e:
        print(f"warning: snapshot history not recorded: {e}", file=sys.stderr)

    if cfg.max_age_days is not None:
        for removed in retention.prune_old_isos(output_dir, cfg.max_age_days):
            print(f"removed old snapshot: {removed}")

    print("note: boot this in a VM before trusting it -- BIOS+UEFI hybrid boot is not self-verifying.")
    return 0


def cmd_packages_list(args: argparse.Namespace) -> int:
    if args.which in ("explicit", "all"):
        for pkg in packages.explicit_packages():
            print(pkg)
    if args.which in ("aur", "local", "all"):
        report = packages.split_foreign_packages(packages.foreign_packages())
        if args.which == "aur":
            for pkg in report.aur_reproducible:
                print(pkg)
        elif args.which == "local":
            for pkg in report.local_only:
                print(pkg)
        else:
            for pkg in report.aur_reproducible + report.local_only:
                print(pkg)
    return 0


def cmd_config_show(_args: argparse.Namespace) -> int:
    cfg = config.load()
    for f in cfg.__dataclass_fields__:
        print(f"{f} = {getattr(cfg, f)!r}")
    return 0


def cmd_config_path(_args: argparse.Namespace) -> int:
    for path, exists in config.config_paths():
        print(f"{'[exists]' if exists else '[absent]'} {path}")
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    try:
        config.set_value(args.key, args.value)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"set {args.key} = {args.value!r} in {constants.USER_CONFIG_FILE}")
    return 0


def cmd_excludes_list(_args: argparse.Namespace) -> int:
    for pattern in excludes.ExcludeList().load():
        print(pattern)
    return 0


def cmd_excludes_add(args: argparse.Namespace) -> int:
    excludes.ExcludeList().add(args.pattern)
    return 0


def cmd_excludes_remove(args: argparse.Namespace) -> int:
    excludes.ExcludeList().remove(args.pattern)
    return 0


def cmd_excludes_reset(_args: argparse.Namespace) -> int:
    try:
        excludes.ExcludeList().reset()
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_excludes_edit(_args: argparse.Namespace) -> int:
    return excludes.ExcludeList().edit()


def cmd_excludes_folders(_args: argparse.Namespace) -> int:
    user_dirs = excludes.resolve_user_dirs()
    for name in constants.NAMED_FOLDERS:
        resolved = user_dirs.get(name)
        print(f"{name}: {resolved if resolved else '(not set)'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mabox-snapshot")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print the version").set_defaults(func=cmd_version)
    sub.add_parser("doctor", help="Check prerequisites, read-only").set_defaults(func=cmd_doctor)

    create_parser = sub.add_parser("create", help="Build a snapshot")
    create_parser.add_argument("--mode", choices=["preserving", "reset"], required=True)
    create_parser.add_argument("-w", "--workdir", type=Path)
    create_parser.add_argument("-o", "--skip-space-check", action="store_true")
    create_parser.add_argument("-m", "--month", action="store_true", help="Name the output by year-month instead of a full timestamp")
    create_parser.add_argument("--output-dir", type=Path)
    create_parser.add_argument("--iso-name")
    create_parser.add_argument("--compression", choices=squashfs.SUPPORTED_COMPRESSORS)
    create_parser.add_argument("--compression-level", type=int)
    create_parser.add_argument("--exclude-list", type=Path)
    create_parser.add_argument("--exclude-folder", action="append", default=[], choices=constants.NAMED_FOLDERS)
    create_parser.add_argument("--kernel")
    create_parser.add_argument("--all-kernels", action="store_true")
    create_parser.add_argument("--dry-run", action="store_true", help="Print the resolved plan and command, execute nothing")
    create_parser.add_argument("--keep-workdir", action="store_true")
    create_parser.add_argument("--max-age-days", type=int, help="Delete older mabox-*.iso files in the output dir after a successful build")
    create_parser.add_argument("--change-threshold-mb", type=int, help="Prompt about home-dir items new/grown by at least this many MiB since the last snapshot (default 200)")
    create_parser.set_defaults(func=cmd_create)

    config_parser = sub.add_parser("config", help="Inspect or edit configuration")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Print the resolved config").set_defaults(func=cmd_config_show)
    config_sub.add_parser("path", help="List config files in load order").set_defaults(func=cmd_config_path)
    set_parser = config_sub.add_parser("set", help="Set a key in the user config")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    set_parser.set_defaults(func=cmd_config_set)

    excludes_parser = sub.add_parser("excludes", help="Manage the exclude list")
    excludes_sub = excludes_parser.add_subparsers(dest="excludes_command", required=True)
    excludes_sub.add_parser("list", help="Print the current exclude list").set_defaults(func=cmd_excludes_list)
    excludes_sub.add_parser("edit", help="Open the exclude list in $EDITOR").set_defaults(func=cmd_excludes_edit)
    excludes_sub.add_parser("reset", help="Restore the shipped default exclude list").set_defaults(func=cmd_excludes_reset)
    excludes_sub.add_parser("folders", help="List named folders and their resolved paths").set_defaults(func=cmd_excludes_folders)
    add_parser = excludes_sub.add_parser("add", help="Add a pattern")
    add_parser.add_argument("pattern")
    add_parser.set_defaults(func=cmd_excludes_add)
    remove_parser = excludes_sub.add_parser("remove", help="Remove a pattern")
    remove_parser.add_argument("pattern")
    remove_parser.set_defaults(func=cmd_excludes_remove)

    packages_parser = sub.add_parser("packages", help="Inspect installed packages")
    packages_sub = packages_parser.add_subparsers(dest="packages_command", required=True)
    list_parser = packages_sub.add_parser("list", help="List packages, read-only, no root")
    list_parser.add_argument(
        "--explicit", dest="which", action="store_const", const="explicit", default="explicit",
        help="Explicit repo packages (default)",
    )
    list_parser.add_argument("--aur", dest="which", action="store_const", const="aur")
    list_parser.add_argument("--local", dest="which", action="store_const", const="local")
    list_parser.add_argument("--all", dest="which", action="store_const", const="all")
    list_parser.set_defaults(func=cmd_packages_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    os.umask(0o022)  # belt-and-suspenders on top of permissions.normalize()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
