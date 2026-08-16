"""Reset-mode account sanitization: replaces every real human account with
a single synthetic demo/demo account in the overlay's copies of
passwd/shadow/group/gshadow/subuid/subgid -- never the live files.
write_sanitized_files() is the only function that does I/O, and it only
ever writes into an overlay directory.

UID_MIN/GID_MIN=1000 is verified from this host's /etc/login.defs (the
standard Arch/Manjaro default) -- accounts and groups at or above it are
human/dynamic, not system, and are the ones sanitized away. This also
resolves a real collision found on this host: a dynamically-created
"autologin" group happened to sit at gid 1000, the same slot demo's own
private group uses here -- since every gid >= GID_MIN is dropped and
replaced wholesale, there's no naming collision in the result.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from . import constants

UID_MIN = 1000
GID_MIN = 1000


def _fields(line: str) -> list[str]:
    return line.rstrip("\n").split(":")


def hash_demo_password(password: str = "demo") -> str:
    result = subprocess.run(["openssl", "passwd", "-6", password], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def sanitize_passwd(lines: list[str], uid_min: int = UID_MIN) -> list[str]:
    kept = [line.rstrip("\n") for line in lines if line.strip() and int(_fields(line)[2]) < uid_min]
    kept.append(
        f"{constants.DEMO_USERNAME}:x:{constants.DEMO_UID}:{constants.DEMO_GID}:"
        f"{constants.DEMO_USERNAME}:/home/{constants.DEMO_USERNAME}:/bin/bash"
    )
    return kept


def system_account_names(passwd_lines: list[str], uid_min: int = UID_MIN) -> set[str]:
    return {_fields(line)[0] for line in passwd_lines if line.strip() and int(_fields(line)[2]) < uid_min}


def sanitize_shadow(lines: list[str], system_names: set[str], password_hash: str) -> list[str]:
    kept = [line.rstrip("\n") for line in lines if line.strip() and _fields(line)[0] in system_names]
    lastchg = int(time.time() // 86400)
    kept.append(f"{constants.DEMO_USERNAME}:{password_hash}:{lastchg}:0:99999:7:::")
    return kept


def sanitize_group(lines: list[str], system_names: set[str], gid_min: int = GID_MIN) -> list[str]:
    kept = []
    for line in lines:
        if not line.strip():
            continue
        name, passwd, gid, members = _fields(line)
        if int(gid) >= gid_min:
            continue
        member_list = [m for m in members.split(",") if m and m in system_names]
        if name in constants.DEMO_BASELINE_GROUPS:
            member_list.append(constants.DEMO_USERNAME)
        kept.append(f"{name}:{passwd}:{gid}:{','.join(member_list)}")
    kept.append(f"{constants.DEMO_USERNAME}:x:{constants.DEMO_GID}:")
    return kept


def sanitize_gshadow(lines: list[str], system_names: set[str], retained_group_names: set[str]) -> list[str]:
    kept = []
    for line in lines:
        if not line.strip():
            continue
        name, passwd, admins, members = _fields(line)
        if name not in retained_group_names:
            continue
        admin_list = [m for m in admins.split(",") if m and m in system_names]
        member_list = [m for m in members.split(",") if m and m in system_names]
        if name in constants.DEMO_BASELINE_GROUPS:
            member_list.append(constants.DEMO_USERNAME)
        kept.append(f"{name}:{passwd}:{','.join(admin_list)}:{','.join(member_list)}")
    kept.append(f"{constants.DEMO_USERNAME}:!::")
    return kept


def sanitize_subid(lines: list[str], system_names: set[str]) -> list[str]:
    """subuid/subgid share the 'name:start:count' format. No demo row is
    added -- a live demo account has no need for user-namespace ranges."""
    return [line.rstrip("\n") for line in lines if line.strip() and _fields(line)[0] in system_names]


# Explicit modes, not left to permissions.normalize()'s later pass -- shadow
# and gshadow must never end up world-readable even transiently, and must
# stay 0640 regardless of what runs before or after this in the pipeline.
WORLD_READABLE_MODE = 0o644
SHADOW_MODE = 0o640


def _write(path: Path, lines: list[str], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" if lines else "")
    path.chmod(mode)


def write_sanitized_files(overlay_dir: Path, source_root: Path = Path("/")) -> None:
    """Reads the live account files under source_root and writes sanitized
    replacements into overlay_dir/etc/*, each explicitly chmod'd (never
    left to the calling process's umask -- see permissions.py)."""
    passwd_lines = (source_root / "etc/passwd").read_text().splitlines()
    shadow_lines = (source_root / "etc/shadow").read_text().splitlines()
    group_lines = (source_root / "etc/group").read_text().splitlines()
    gshadow_lines = (source_root / "etc/gshadow").read_text().splitlines()
    subuid_path = source_root / "etc/subuid"
    subgid_path = source_root / "etc/subgid"
    subuid_lines = subuid_path.read_text().splitlines() if subuid_path.exists() else []
    subgid_lines = subgid_path.read_text().splitlines() if subgid_path.exists() else []

    system_names = system_account_names(passwd_lines)
    password_hash = hash_demo_password()

    new_passwd = sanitize_passwd(passwd_lines)
    new_group = sanitize_group(group_lines, system_names)
    retained_group_names = {_fields(line)[0] for line in new_group}

    _write(overlay_dir / "etc/passwd", new_passwd, WORLD_READABLE_MODE)
    _write(overlay_dir / "etc/shadow", sanitize_shadow(shadow_lines, system_names, password_hash), SHADOW_MODE)
    _write(overlay_dir / "etc/group", new_group, WORLD_READABLE_MODE)
    _write(
        overlay_dir / "etc/gshadow",
        sanitize_gshadow(gshadow_lines, system_names, retained_group_names),
        SHADOW_MODE,
    )
    _write(overlay_dir / "etc/subuid", sanitize_subid(subuid_lines, system_names), WORLD_READABLE_MODE)
    _write(overlay_dir / "etc/subgid", sanitize_subid(subgid_lines, system_names), WORLD_READABLE_MODE)
