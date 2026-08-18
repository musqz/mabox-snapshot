"""argparse dispatch for the mabox-snapshot CLI."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from . import backup, calamares, changes, config, constants, excludes, grubcfg, history, isobuild, kernels, luks, overlay, packages, permissions, privilege, profiles, retention, skelaudit, squashfs
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
    if args.encrypt:
        overrides["encrypt"] = True
    if args.backup_to:
        overrides["backup_destinations"] = tuple(args.backup_to)
    if args.profile is not None:
        overrides["profile"] = args.profile
    return replace(cfg, **overrides)


def cmd_create(args: argparse.Namespace) -> int:
    cfg = _apply_create_overrides(config.load(), args)

    if cfg.encrypt and args.mode == "reset":
        print("error: --encrypt is not supported with --mode reset (reset mode only ever contains the synthetic demo account)", file=sys.stderr)
        return 1

    output_dir = cfg.output_dir or cfg.workdir
    plan = overlay.resolve_plan(args.mode, cfg.workdir, cfg.exclude_list, cfg.exclude_folders, output_dir=output_dir)

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

    # Resolved for every detected kernel, not just selected -- cheap (a few
    # extra local pacman -Ql calls), and profiles.py's kernel-module
    # trimming needs every non-selected kernel's version too. A resolution
    # failure is only a hard error for a kernel this build actually needs;
    # exclude_unselected_kernel_modules() defensively skips a kernel absent
    # from kvers rather than erroring.
    kvers = {}
    for k in detected:
        kver = kernels.module_version(k)
        if kver is not None:
            kvers[k.name] = kver
    for k in selected:
        if k.name not in kvers:
            print(f"error: could not resolve {k.name!r} to a /usr/lib/modules/<version> (pacman -Ql {k.name})", file=sys.stderr)
            return 1

    try:
        profile = profiles.resolve(cfg.profile)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if profile.extra_excludes:
        plan.layers[0].exclude_patterns.extend(profile.extra_excludes)
    if profile.trim_unselected_kernel_modules:
        plan.layers[0].exclude_patterns.extend(
            excludes.exclude_unselected_kernel_modules(detected, selected, kvers)
        )
    plan.layers[0].exclude_patterns = list(dict.fromkeys(plan.layers[0].exclude_patterns))

    stamp = datetime.now().strftime("%Y-%m" if cfg.month else "%Y-%m-%d-%H%M")
    iso_name = args.iso_name or f"{constants.ISO_NAME_PREFIX}{args.mode}-{stamp}"
    dest = output_dir / f"{iso_name}.iso"

    iso_root = cfg.workdir / "iso"
    mkinitcpio_conf = cfg.workdir / "mkinitcpio-miso.conf"

    # For --encrypt builds, build_unpackfs_conf() points the rootfs entry at
    # the live session's already-decrypted mount instead of the on-media
    # squashfs (see its docstring) -- always generated, never skipped.
    unpackfs_conf_path = cfg.workdir / "unpackfs.conf"
    unpackfs_pseudo = calamares.unpackfs_pseudo_specs(unpackfs_conf_path)
    # Always the rootfs layer (plan.layers[0] in both modes, same as the
    # "new_excludes" case further down): without this, a real file already
    # sitting at that path (e.g. a hand-placed admin workaround for this
    # very bug) would silently win over our pseudo-file -- verified
    # empirically, mksquashfs just warns and keeps whatever's already in
    # the source tree.
    plan.layers[0].exclude_patterns.append(calamares.UNPACKFS_CONF_PATH)

    # Per-layer destinations (see overlay.py's module docstring for why
    # each layer is built by its own single-source mksquashfs invocation).
    # --encrypt only ever applies to preserving mode's sole "rootfs" layer
    # (validated above): its plaintext squashfs stays in workdir, never
    # under iso_root -- the ISO tree only ever gets the encrypted
    # container (see luks.py).
    layer_dest = {}
    layer_luks_dest = {}
    for layer in plan.layers:
        if cfg.encrypt and layer.name == "rootfs":
            layer_dest[layer.name] = cfg.workdir / f"{layer.name}.sfs"
            layer_luks_dest[layer.name] = (
                iso_root / constants.MISO_BASEDIR / constants.ISO_ARCH / f"{layer.name}.sfs{constants.LUKS_CONTAINER_SUFFIX}"
            )
        else:
            layer_dest[layer.name] = iso_root / constants.MISO_BASEDIR / constants.ISO_ARCH / f"{layer.name}.sfs"
    exclude_files = {
        layer.name: (cfg.workdir / f"exclude-{layer.name}.list" if layer.exclude_patterns else None)
        for layer in plan.layers
    }

    splash_source = constants.IMAGES_DIR / "splash.png"
    has_splash = splash_source.exists()
    splash_dest = iso_root / "boot" / "grub" / "splash.png"

    branding = calamares.load_branding() if args.mode == "reset" else None

    layer_cmds = {
        layer.name: squashfs.build_command(
            [layer.source], layer_dest[layer.name], exclude_files[layer.name], cfg.compression, cfg.compression_level,
            pseudo_files=unpackfs_pseudo if layer.name == "rootfs" else None,
        )
        for layer in plan.layers
    }
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
    print(f"profile:     {profile.name}")
    for layer in plan.layers:
        print(f"source:      [{layer.name}] {layer.source} ({len(layer.exclude_patterns)} exclude pattern(s))")
    print(f"kernels:     {', '.join(f'{k.name} ({kvers[k.name]})' for k in selected)}")
    level = f" (level {cfg.compression_level})" if cfg.compression_level is not None else ""
    print(f"compression: {cfg.compression}{level}")
    print(f"workdir:     {cfg.workdir}")
    print(f"output:      {dest}")
    for layer in plan.layers:
        print(f"squashfs:    [{layer.name}] {' '.join(str(c) for c in layer_cmds[layer.name])}")
    print(f"encryption:  {'LUKS2 (rootfs.sfs.luks, passphrase prompted at build time)' if cfg.encrypt else 'none'}")
    for cmd in initramfs_cmds:
        print(f"initramfs:   {' '.join(str(c) for c in cmd)}")
    if has_splash:
        print(f"splash:      {' '.join(str(c) for c in grubcfg.build_splash_command(splash_source, splash_dest))}")
    else:
        print(f"splash:      none configured ({splash_source} not found) -- plain grub boot menu")
    if args.mode == "reset":
        note = f"{len(branding.slides)} slide(s) from {constants.IMAGES_DIR}" if branding else "none configured -- stock Manjaro branding"
        print(f"calamares:   {note}")
    if cfg.encrypt:
        print(f"unpackfs:    {', '.join(layer.name for layer in plan.layers)} -> {unpackfs_conf_path} (rootfs sourced from live decrypted mount, not on-media squashfs)")
    else:
        print(f"unpackfs:    {', '.join(layer.name for layer in plan.layers)} -> {unpackfs_conf_path}")
    print(f"bios boot:   {' '.join(str(c) for c in bios_cmd)}")
    print(f"efi boot:    {' '.join(str(c) for c in efi_cmd)}")
    print(f"assemble:    {' '.join(str(c) for c in xorriso_cmd)}")
    print(f"backup:      {', '.join(cfg.backup_destinations) if cfg.backup_destinations else 'none configured'}")

    if args.dry_run:
        return 0

    try:
        privilege.require_root("mabox-snapshot create")
    except privilege.NotRootError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    passphrase = None
    if cfg.encrypt:
        try:
            luks.check_hook_installed()
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        try:
            passphrase = luks.prompt_for_passphrase()
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    workdir_mod.ensure_workdir(cfg.workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for layer in plan.layers:
        layer_dest[layer.name].parent.mkdir(parents=True, exist_ok=True)
        if layer.name in layer_luks_dest:
            layer_luks_dest[layer.name].parent.mkdir(parents=True, exist_ok=True)

    # No staging copy exists to size precisely (mksquashfs reads live '/' directly).
    # The final ISO embeds the same bytes again (ISO9660 is a monolithic image, not
    # a reference format), so budget one squashfs_estimate share for the squashfs
    # itself (always staged under workdir) and another for the ISO (written to
    # output_dir, which defaults to workdir but may be a separate --output-dir
    # mount -- e.g. an external drive -- in which case it needs its own check).
    squashfs_estimate = int(shutil.disk_usage("/").used * 0.5)
    workdir_required = squashfs_estimate if output_dir != cfg.workdir else squashfs_estimate * 2
    if cfg.encrypt:
        workdir_required += squashfs_estimate  # plaintext temp + encrypted container coexist briefly
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
                # Always the rootfs layer (plan.layers[0] in both modes):
                # it's the only layer whose source is the live filesystem
                # this scan just walked.
                rootfs_layer = plan.layers[0]
                rootfs_layer.exclude_patterns.extend(new_excludes)
                if exclude_files[rootfs_layer.name] is None:
                    exclude_files[rootfs_layer.name] = cfg.workdir / f"exclude-{rootfs_layer.name}.list"
    except Exception as e:
        print(f"warning: change notification skipped: {e}", file=sys.stderr)

    try:
        overlay.build_overlay(plan)  # no-op for preserving mode
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    unpackfs_conf_path.write_text(
        calamares.build_unpackfs_conf([layer.name for layer in plan.layers], encrypt=cfg.encrypt)
    )

    for layer in plan.layers:
        if exclude_files[layer.name] is not None:
            excludes.write_mksquashfs_exclude_file(layer.exclude_patterns, exclude_files[layer.name])
        squashfs.build(
            [layer.source], layer_dest[layer.name], exclude_files[layer.name], cfg.compression, cfg.compression_level,
            pseudo_files=unpackfs_pseudo if layer.name == "rootfs" else None,
        )
        if cfg.encrypt and layer.name == "rootfs":
            luks.encrypt_squashfs(layer_dest[layer.name], layer_luks_dest[layer.name], passphrase)

    (iso_root / "boot").mkdir(parents=True, exist_ok=True)
    if cfg.encrypt:
        isobuild.write_mkinitcpio_conf(mkinitcpio_conf, constants.MKINITCPIO_MISO_LUKS_MODULES, constants.MKINITCPIO_MISO_LUKS_HOOKS)
    else:
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

    if cfg.backup_destinations:
        for failed in backup.push_to_destinations(dest, cfg.backup_destinations):
            print(f"warning: backup to {failed} failed", file=sys.stderr)

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


def cmd_excludes_rules_list(args: argparse.Namespace) -> int:
    rules = excludes.OverrideRuleList().load()
    for orphan in excludes.find_orphan_includes(rules):
        print(f"warning: 'include {orphan.pattern}' has no enclosing exclude rule -- no-op", file=sys.stderr)

    if not args.compiled:
        for rule in rules:
            print(f"{rule.action} {rule.pattern}")
        return 0

    try:
        compiled = excludes.compile_override_rules(rules)
    except (ValueError, excludes.UnsupportedRuleNestingError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not compiled:
        print("(no rules produce any exclude pattern on this host)", file=sys.stderr)
    for pattern in compiled:
        print(pattern)
    return 0


def cmd_excludes_rules_add(args: argparse.Namespace) -> int:
    excludes.OverrideRuleList().add(args.action, args.pattern)
    return 0


def cmd_excludes_rules_remove(args: argparse.Namespace) -> int:
    excludes.OverrideRuleList().remove(args.action, args.pattern)
    return 0


def cmd_excludes_rules_clear(_args: argparse.Namespace) -> int:
    excludes.OverrideRuleList().clear()
    return 0


def cmd_excludes_rules_edit(_args: argparse.Namespace) -> int:
    return excludes.OverrideRuleList().edit()


def cmd_skel_audit(args: argparse.Namespace) -> int:
    home = args.home or Path.home()
    try:
        report = skelaudit.audit_home_against_skel(home)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(skelaudit.format_report(report, show_identical=args.show_identical))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mabox-snapshot")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print the version").set_defaults(func=cmd_version)
    sub.add_parser("doctor", help="Check prerequisites, read-only").set_defaults(func=cmd_doctor)

    create_parser = sub.add_parser(
        "create",
        help="Build a snapshot",
        description="Build a bootable live/install ISO from the running system.",
        epilog=(
            "example:\n"
            "  mabox-snapshot create --mode reset --output-dir /mnt/usb --all-kernels\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_parser.add_argument(
        "--mode", choices=["preserving", "reset"], required=True,
        help=(
            "preserving: full personal clone (real /home, real accounts, real passwords; "
            "optionally --encrypt). reset: sanitized ISO for sharing (synthetic demo/demo "
            "account, no real /home, no saved credentials)"
        ),
    )
    create_parser.add_argument(
        "-w", "--workdir", type=Path,
        help=f"Scratch directory for build state -- squashfs layers, ISO tree, mkinitcpio config (default: {constants.DEFAULT_WORKDIR})",
    )
    create_parser.add_argument(
        "-o", "--skip-space-check", action="store_true",
        help="Skip the free-space precheck on workdir/output-dir before building",
    )
    create_parser.add_argument("-m", "--month", action="store_true", help="Name the output by year-month instead of a full timestamp")
    create_parser.add_argument(
        "--output-dir", type=Path,
        help="Directory the finished ISO is written to (default: same as --workdir)",
    )
    create_parser.add_argument(
        "--iso-name",
        help="Base filename for the ISO, without .iso (default: mabox-<mode>-<timestamp>)",
    )
    create_parser.add_argument(
        "--compression", choices=squashfs.SUPPORTED_COMPRESSORS,
        help="Squashfs compression algorithm passed to mksquashfs -comp (default: zstd)",
    )
    create_parser.add_argument(
        "--compression-level", type=int,
        help="Compression level passed to mksquashfs -Xcompression-level (valid range depends on --compression; default: mksquashfs's own default)",
    )
    create_parser.add_argument(
        "--exclude-list", type=Path,
        help=f"Path to a custom exclude-pattern file, replacing the default list (default: {constants.EXCLUDES_LIST_FILE})",
    )
    create_parser.add_argument(
        "--exclude-folder", action="append", default=[], choices=constants.NAMED_FOLDERS,
        help="Exclude a named XDG user folder from the snapshot in addition to --exclude-list; repeatable",
    )
    create_parser.add_argument(
        "--kernel",
        help="Only include this installed kernel, matched against mkinitcpio presets (default: newest installed kernel)",
    )
    create_parser.add_argument(
        "--all-kernels", action="store_true",
        help="Include every installed kernel instead of just the newest",
    )
    create_parser.add_argument("--dry-run", action="store_true", help="Print the resolved plan and command, execute nothing")
    create_parser.add_argument(
        "--keep-workdir", action="store_true",
        help="No-op for now: workdir cleanup isn't implemented yet, so build state under --workdir is always kept",
    )
    create_parser.add_argument("--max-age-days", type=int, help="Delete older mabox-*.iso files in the output dir after a successful build")
    create_parser.add_argument("--change-threshold-mb", type=int, help="Prompt about home-dir items new/grown by at least this many MiB since the last snapshot (default 200)")
    create_parser.add_argument("--encrypt", action="store_true", help="Encrypt rootfs.sfs with LUKS2 (preserving mode only; passphrase prompted interactively at build time)")
    create_parser.add_argument("--backup-to", action="append", default=[], help="rsync the finished ISO here (local path or user@host:path); repeatable")
    create_parser.add_argument(
        "--profile", choices=list(profiles.PROFILES),
        help="Size/completeness tier: full (default, today's behavior) or lean (trims unselected kernels' "
             "module trees plus VM/container storage; see 'mabox-snapshot skel audit' to curate further)",
    )
    create_parser.set_defaults(func=cmd_create)

    config_parser = sub.add_parser("config", help="Inspect or edit configuration")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Print the resolved config").set_defaults(func=cmd_config_show)
    config_sub.add_parser("path", help="List config files in load order").set_defaults(func=cmd_config_path)
    set_parser = config_sub.add_parser("set", help="Set a key in the user config")
    set_parser.add_argument("key", help="Config key to set (see: mabox-snapshot config show)")
    set_parser.add_argument("value", help="Value to store for that key, written into the TOML config as a quoted string")
    set_parser.set_defaults(func=cmd_config_set)

    excludes_parser = sub.add_parser("excludes", help="Manage the exclude list")
    excludes_sub = excludes_parser.add_subparsers(dest="excludes_command", required=True)
    excludes_sub.add_parser("list", help="Print the current exclude list").set_defaults(func=cmd_excludes_list)
    excludes_sub.add_parser("edit", help="Open the exclude list in $EDITOR").set_defaults(func=cmd_excludes_edit)
    excludes_sub.add_parser("reset", help="Restore the shipped default exclude list").set_defaults(func=cmd_excludes_reset)
    excludes_sub.add_parser("folders", help="List named folders and their resolved paths").set_defaults(func=cmd_excludes_folders)
    add_parser = excludes_sub.add_parser("add", help="Add a pattern")
    add_parser.add_argument("pattern", help="mksquashfs -ef exclude pattern, relative to /, e.g. var/cache/*")
    add_parser.set_defaults(func=cmd_excludes_add)
    remove_parser = excludes_sub.add_parser("remove", help="Remove a pattern")
    remove_parser.add_argument("pattern", help="Exact pattern to remove, as printed by 'excludes list'")
    remove_parser.set_defaults(func=cmd_excludes_remove)

    rules_parser = excludes_sub.add_parser(
        "rules", help="Ordered include/exclude override rules (e.g. exclude a dir but keep one subpath inside it)"
    )
    rules_sub = rules_parser.add_subparsers(dest="rules_command", required=True)
    rules_list_parser = rules_sub.add_parser("list", help="Print the current override rules")
    rules_list_parser.add_argument(
        "--compiled", action="store_true",
        help="Print the flat mksquashfs exclude patterns these rules compile to on this host, instead of the raw rules",
    )
    rules_list_parser.set_defaults(func=cmd_excludes_rules_list)
    rules_add_parser = rules_sub.add_parser("add", help="Add an override rule")
    rules_add_parser.add_argument("action", choices=["exclude", "include"])
    rules_add_parser.add_argument("pattern", help="Path relative to /, e.g. home/*/Documents; glob allowed on exclude rules only")
    rules_add_parser.set_defaults(func=cmd_excludes_rules_add)
    rules_remove_parser = rules_sub.add_parser("remove", help="Remove an override rule")
    rules_remove_parser.add_argument("action", choices=["exclude", "include"])
    rules_remove_parser.add_argument("pattern", help="Exact pattern to remove, as printed by 'excludes rules list'")
    rules_remove_parser.set_defaults(func=cmd_excludes_rules_remove)
    rules_sub.add_parser("clear", help="Remove all override rules").set_defaults(func=cmd_excludes_rules_clear)
    rules_sub.add_parser("edit", help="Open the override-rules file in $EDITOR").set_defaults(func=cmd_excludes_rules_edit)

    packages_parser = sub.add_parser("packages", help="Inspect installed packages")
    packages_sub = packages_parser.add_subparsers(dest="packages_command", required=True)
    list_parser = packages_sub.add_parser("list", help="List packages, read-only, no root")
    list_parser.add_argument(
        "--explicit", dest="which", action="store_const", const="explicit", default="explicit",
        help="Explicit repo packages (default)",
    )
    list_parser.add_argument(
        "--aur", dest="which", action="store_const", const="aur",
        help="Foreign (non-repo) packages that are reproducible from the AUR",
    )
    list_parser.add_argument(
        "--local", dest="which", action="store_const", const="local",
        help="Foreign (non-repo) packages not found in the AUR -- hand-built or removed upstream",
    )
    list_parser.add_argument(
        "--all", dest="which", action="store_const", const="all",
        help="--explicit, --aur, and --local combined",
    )
    list_parser.set_defaults(func=cmd_packages_list)

    skel_parser = sub.add_parser("skel", help="Compare your desktop config against Mabox's shipped defaults")
    skel_sub = skel_parser.add_subparsers(dest="skel_command", required=True)
    audit_parser = skel_sub.add_parser(
        "audit",
        help="Report which of your desktop config files differ from mabox-skel's defaults",
        description=(
            "Reporting only -- nothing here changes what a snapshot captures. Diffs your home "
            "directory against the vendored mabox-skel baseline to show what's untouched, what "
            "you've customized, what you've deleted, and what's fully your own (not from Mabox). "
            "Use the 'differs' list to decide what's worth protecting with "
            "'excludes rules add include ...' in a leaner snapshot profile."
        ),
    )
    audit_parser.add_argument("--home", type=Path, help="Home directory to audit (default: your own)")
    audit_parser.add_argument("--show-identical", action="store_true", help="Also list untouched (identical-to-default) paths")
    audit_parser.set_defaults(func=cmd_skel_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    os.umask(0o022)  # belt-and-suspenders on top of permissions.normalize()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
