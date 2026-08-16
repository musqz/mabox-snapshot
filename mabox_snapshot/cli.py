"""argparse dispatch for the mabox-snapshot CLI."""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from . import config, constants, excludes, kernels, packages
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
