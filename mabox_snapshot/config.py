"""Cascading config: built-in defaults -> system file -> user file -> CLI flags."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

from . import constants


@dataclass
class SnapshotConfig:
    workdir: Path = constants.DEFAULT_WORKDIR
    output_dir: Path | None = None  # None => workdir
    compression: str = "zstd"
    compression_level: int | None = None
    exclude_list: Path = constants.EXCLUDES_LIST_FILE
    exclude_folders: tuple[str, ...] = ()
    kernel: str | None = None
    all_kernels: bool = False
    demo_lang: str = constants.DEFAULT_DEMO_LANG
    no_calamares: bool = False
    skip_space_check: bool = False
    keep_workdir: bool = False
    month: bool = False
    max_age_days: int | None = None
    change_threshold_mb: int = 200
    encrypt: bool = False
    backup_destinations: tuple[str, ...] = ()
    profile: str = "full"


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _coerce(raw: dict) -> dict:
    """Convert TOML-friendly string/list values into the dataclass's field types."""
    out = dict(raw)
    if "workdir" in out:
        out["workdir"] = Path(out["workdir"])
    if "output_dir" in out and out["output_dir"] is not None:
        out["output_dir"] = Path(out["output_dir"])
    if "exclude_list" in out:
        out["exclude_list"] = Path(out["exclude_list"])
    if "exclude_folders" in out:
        out["exclude_folders"] = tuple(out["exclude_folders"])
    if "backup_destinations" in out:
        out["backup_destinations"] = tuple(out["backup_destinations"])
    return out


def load(system_path: Path = constants.SYSTEM_CONFIG_FILE,
         user_path: Path = constants.USER_CONFIG_FILE) -> SnapshotConfig:
    """Resolve the cascade: defaults -> system file -> user file. CLI flags are
    applied afterward by the caller (cli.py), via dataclasses.replace()."""
    cfg = SnapshotConfig()
    known = {f.name for f in fields(SnapshotConfig)}

    for path in (system_path, user_path):
        raw = _coerce(_load_toml(path))
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"{path}: unknown config key(s): {', '.join(sorted(unknown))}")
        cfg = replace(cfg, **raw)

    return cfg


def config_paths(system_path: Path = constants.SYSTEM_CONFIG_FILE,
                  user_path: Path = constants.USER_CONFIG_FILE) -> list[tuple[Path, bool]]:
    """Returns [(path, exists)] for every config file in the cascade, in load order."""
    return [(p, p.exists()) for p in (system_path, user_path)]


def set_value(key: str, value: str, user_path: Path = constants.USER_CONFIG_FILE) -> None:
    """Targeted line replace/insert in the user config file -- avoids needing a
    write-capable TOML library just for this one command."""
    known = {f.name for f in fields(SnapshotConfig)}
    if key not in known:
        raise ValueError(f"unknown config key: {key}")

    user_path.parent.mkdir(parents=True, exist_ok=True)
    lines = user_path.read_text().splitlines() if user_path.exists() else []

    new_line = f'{key} = "{value}"'
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key} ") or line.strip().startswith(f"{key}="):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)

    user_path.write_text("\n".join(lines) + "\n")
