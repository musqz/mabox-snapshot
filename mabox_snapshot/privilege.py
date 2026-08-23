"""Root check. No silent sudo re-exec -- the user runs `sudo mabox-snapshot ...` themselves."""

import os
import sys
from pathlib import Path


class NotRootError(RuntimeError):
    pass


class NoSudoUserError(RuntimeError):
    pass


def require_root(action: str) -> None:
    if os.geteuid() != 0:
        raise NotRootError(f"{action} requires root -- re-run with sudo.")


def is_root() -> bool:
    return os.geteuid() == 0


def resolve_home_dir() -> Path:
    """The real invoking user's home dir under sudo. This tool never silently
    re-execs and always runs as `sudo mabox-snapshot ...`, so SUDO_USER is
    expected to be set -- Path.home() would resolve to /root here and
    silently point at the wrong tree, so an unset SUDO_USER is a hard error,
    not a guess."""
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user:
        raise NoSudoUserError("SUDO_USER is not set -- run via 'sudo mabox-snapshot ...'")
    return Path(f"/home/{sudo_user}")


def resolve_effective_home() -> Path:
    """The home dir this invocation's own per-user files (excludes backups,
    etc.) belong under. Some excludes subcommands (backups save/list) need
    no root and may be run bare; others (reset, backups restore) always run
    under sudo -- resolve_home_dir() there, since Path.home() would silently
    resolve to /root's. Path.home() otherwise, for a genuinely unprivileged
    invocation."""
    return resolve_home_dir() if is_root() else Path.home()


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)
