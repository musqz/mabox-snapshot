"""Encrypts a preserving-mode ISO's rootfs.sfs payload with LUKS2 so a
passphrase is required at boot to unlock and mount the root filesystem --
real protection for the personal data inside, unlike a GRUB menu password
alone (which only gates the boot menu, never the squashfs contents). This
is opt-in (--encrypt), preserving mode only. Boot-side unlock happens via
a custom miso_luks mkinitcpio hook (see configs/initcpio/) -- this module
only handles the build-time encrypt step.

Same command-builder/executor split as squashfs.py/isobuild.py: the
build_*_command() functions are pure and unit-tested; the functions that
actually run them (real losetup/cryptsetup, needs root) are thin
subprocess.run() wrappers and are not unit-tested -- same untested-
execution-layer precedent as squashfs.build()/isobuild.build_initramfs()/
isobuild.assemble()."""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

from . import constants

# 32 MiB margin over LUKS2's ~16 MiB default header. Lives here, not in
# constants.py -- a sizing implementation detail, same reasoning as
# squashfs.py's own local SUPPORTED_COMPRESSORS. The container file is
# sparse, so a generous margin costs nothing at rest.
LUKS_HEADER_MARGIN_BYTES = 32 * 1024 * 1024


def container_size_bytes(plaintext_size_bytes: int, margin_bytes: int = LUKS_HEADER_MARGIN_BYTES) -> int:
    return plaintext_size_bytes + margin_bytes


def create_container_file(container: Path, size_bytes: int) -> None:
    container.touch()
    os.truncate(container, size_bytes)  # sparse -- payload isn't written yet


def build_luks_format_command(container: Path) -> list[str]:
    # -q/--batch-mode: without it, cryptsetup's interactive "this will
    # overwrite data, are you sure?" confirmation would itself try to read
    # from stdin, colliding with --key-file=-.
    return ["cryptsetup", "luksFormat", "-q", "--type", "luks2", "--key-file=-", str(container)]


def build_losetup_attach_command(container: Path) -> list[str]:
    # No --read-only: the build-time attach must accept writes (dd writes
    # the plaintext payload onto the resulting /dev/mapper device).
    # Contrast with the boot-time hook's own losetup call in miso_luks,
    # which does use --read-only, mirroring stock _mnt_sfs().
    return ["losetup", "--find", "--show", str(container)]


def build_losetup_detach_command(loop_dev: str) -> list[str]:
    return ["losetup", "-d", loop_dev]


def build_luks_open_command(loop_dev: str, mapper_name: str) -> list[str]:
    return ["cryptsetup", "open", "--type", "luks2", "--key-file=-", loop_dev, mapper_name]


def build_luks_close_command(mapper_name: str) -> list[str]:
    return ["cryptsetup", "close", mapper_name]


def build_dd_copy_command(src: Path, mapper_dev: str, block_size: str = "4M") -> list[str]:
    # bs=4M: POSIX dd's 512-byte default means millions of syscalls against
    # a multi-GB squashfs -- a real performance problem, not theoretical.
    # conv=fsync is a correctness requirement, not just performance: without
    # it, writes could still be page-cache-buffered when close_container()/
    # detach_loop() tear the mapping down immediately after in the same
    # function, risking silent truncation of the encrypted payload.
    return ["dd", f"if={src}", f"of={mapper_dev}", f"bs={block_size}", "status=progress", "conv=fsync"]


def check_hook_installed(hook_path: Path = constants.MISO_LUKS_HOOK_INSTALLED) -> None:
    if not hook_path.exists():
        raise FileNotFoundError(
            f"LUKS boot hook not found at {hook_path} -- is mabox-snapshot installed via its package?"
        )


def prompt_for_passphrase() -> str:
    """getpass twice with a match check (mirrors passwd's UX convention).
    Never reads a passphrase from a flag, env var, or file. Hard-fails if
    stdin isn't a tty -- deliberately different from
    changes.prompt_for_exclusions()'s graceful non-interactive degrade,
    because there's no safe silent default here: proceeding without a real
    passphrase when --encrypt was explicitly requested would silently
    defeat the whole feature."""
    if not sys.stdin.isatty():
        raise RuntimeError(
            "--encrypt requires an interactive terminal to prompt for a passphrase "
            "(no passphrase is ever read from a flag or environment variable)"
        )
    while True:
        p1 = getpass.getpass("LUKS passphrase for the encrypted rootfs: ")
        if not p1:
            print("error: passphrase must not be empty", file=sys.stderr)
            continue
        p2 = getpass.getpass("Confirm passphrase: ")
        if p1 != p2:
            print("error: passphrases did not match, try again", file=sys.stderr)
            continue
        return p1


def attach_loop(container: Path) -> str:
    result = subprocess.run(build_losetup_attach_command(container), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def detach_loop(loop_dev: str) -> None:
    subprocess.run(build_losetup_detach_command(loop_dev), check=True)


def format_container(container: Path, passphrase: str) -> None:
    subprocess.run(build_luks_format_command(container), input=passphrase.encode(), check=True)


def open_container(loop_dev: str, mapper_name: str, passphrase: str) -> None:
    subprocess.run(build_luks_open_command(loop_dev, mapper_name), input=passphrase.encode(), check=True)


def close_container(mapper_name: str) -> None:
    subprocess.run(build_luks_close_command(mapper_name), check=True)


def copy_plaintext_onto_mapper(plaintext: Path, mapper_name: str) -> None:
    subprocess.run(build_dd_copy_command(plaintext, f"/dev/mapper/{mapper_name}"), check=True)


def encrypt_squashfs(
    plaintext: Path,
    container_dest: Path,
    passphrase: str,
    mapper_name: str = constants.ISO_LUKS_MAPPER_NAME,
) -> None:
    """Encrypts plaintext (a plain squashfs file) into container_dest (a
    LUKS2 container holding the same bytes). Cleans up loop devices and
    open mappers even on failure, and always removes the plaintext copy
    (success or failure) so it never lingers on disk."""
    loop_dev = None
    opened = False
    try:
        create_container_file(container_dest, container_size_bytes(plaintext.stat().st_size))
        format_container(container_dest, passphrase)
        loop_dev = attach_loop(container_dest)
        open_container(loop_dev, mapper_name, passphrase)
        opened = True
        copy_plaintext_onto_mapper(plaintext, mapper_name)
    finally:
        if opened:
            close_container(mapper_name)
        if loop_dev:
            detach_loop(loop_dev)
        plaintext.unlink(missing_ok=True)
