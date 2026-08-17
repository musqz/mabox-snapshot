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


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)
