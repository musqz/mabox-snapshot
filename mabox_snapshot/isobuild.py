"""BIOS+UEFI boot images, the live initramfs, and the final xorriso ISO --
modeled directly on Manjaro's own /usr/lib/manjaro-tools/util-iso.sh
(assemble_iso) and util-iso-boot.sh (prepare_grub), both verified present
and read on this host. Deliberately dropped as out of scope for a
single-rootfs personal-snapshot tool: GPG signing, snap seeding, the
desktopfs/mhwdfs multi-layer split, and grubenv's menu_show_once
persistence flag.

The FAT efi.img is built with a plain `mount -o loop` (auto-managed loop
device) rather than manjaro-tools' manual losetup/track_img bookkeeping --
that bookkeeping exists there to support several concurrently-mounted
images; this tool only ever builds one.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from . import constants

MKINITCPIO_CONF_TEMPLATE = 'MODULES=({modules})\nHOOKS=({hooks})\nCOMPRESSION="xz"\n'


def write_mkinitcpio_conf(
    dest: Path,
    modules: list[str] = constants.MKINITCPIO_MISO_MODULES,
    hooks: list[str] = constants.MKINITCPIO_MISO_HOOKS,
) -> Path:
    dest.write_text(
        MKINITCPIO_CONF_TEMPLATE.format(modules=" ".join(modules), hooks=" ".join(hooks))
    )
    return dest


def build_mkinitcpio_command(kver: str, conf_path: Path, dest: Path) -> list[str]:
    return ["mkinitcpio", "-k", kver, "-c", str(conf_path), "-g", str(dest)]


def check_miso_hooks_installed(
    hooks: list[str] = constants.MISO_EXTERNAL_HOOKS,
    search_dirs: list[Path] = constants.MISO_HOOK_SEARCH_DIRS,
) -> None:
    missing = [h for h in hooks if not any((d / h).exists() for d in search_dirs)]
    if missing:
        raise FileNotFoundError(
            "missing mkinitcpio hook(s) required for the live-boot initramfs: "
            + ", ".join(missing)
            + " -- install manjaro-tools-iso-git (pacman -S manjaro-tools-iso-git)"
        )


def check_miso_hook_binaries_installed(binaries: list[str] = constants.MISO_EXTERNAL_BINARIES) -> None:
    missing = [b for b in binaries if shutil.which(b) is None]
    if missing:
        raise FileNotFoundError(
            "missing binary(ies) required by the live-boot initramfs hooks: "
            + ", ".join(missing)
            + " -- install nbd and/or curl (pacman -S nbd curl)"
        )


def build_initramfs(kver: str, conf_path: Path, dest: Path) -> None:
    subprocess.run(build_mkinitcpio_command(kver, conf_path, dest), check=True)


def build_bios_boot_command(grub_i386pc_dir: Path) -> list[str]:
    return [
        "grub-mkimage",
        "-d", str(grub_i386pc_dir),
        "-o", str(grub_i386pc_dir / "core.img"),
        "-O", "i386-pc",
        "-p", "/boot/grub",
        "biosdisk", "iso9660",
    ]


def prepare_bios_boot(iso_root: Path) -> None:
    """Populates iso_root/boot/grub/i386-pc/{core,eltorito,boot_hybrid}.img."""
    dest = iso_root / "boot" / "grub" / "i386-pc"
    dest.mkdir(parents=True, exist_ok=True)
    src = constants.GRUB_LIB_DIR / "i386-pc"
    for item in src.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)

    subprocess.run(build_bios_boot_command(dest), check=True)

    with (dest / "eltorito.img").open("wb") as out:
        out.write((dest / "cdboot.img").read_bytes())
        out.write((dest / "core.img").read_bytes())


def build_efi_boot_command(grub_efi_dir: Path, dest: Path) -> list[str]:
    return [
        "grub-mkimage",
        "-d", str(grub_efi_dir),
        "-o", str(dest),
        "-O", "x86_64-efi",
        "-p", "/boot/grub",
        "iso9660",
    ]


def _build_fat_image(dest: Path, source_file: Path, arcname: str, size_bytes: int) -> None:
    dest.write_bytes(b"\0" * size_bytes)
    subprocess.run(["mkfs.fat", "-n", "MISO_EFI", str(dest)], check=True, capture_output=True)

    mnt = dest.parent / f".{dest.name}.mnt"
    mnt.mkdir(exist_ok=True)
    subprocess.run(["mount", "-o", "loop", str(dest), str(mnt)], check=True)
    try:
        target = mnt / arcname
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
    finally:
        subprocess.run(["umount", str(mnt)], check=True)
        mnt.rmdir()


def prepare_efi_boot(iso_root: Path, work_dir: Path, efi_img_size: int = 4 * 1024 * 1024) -> None:
    """Builds bootx64.efi, drops a plain copy at iso_root/efi/boot/ (for
    firmware that boots the ISO9660 tree directly), and builds the
    FAT-formatted efi.img that assemble()'s xorriso call appends as a raw
    partition. Needs root: mkfs.fat + a loop mount."""
    efi_src = work_dir / "grub-x86_64-efi"
    efi_src.mkdir(parents=True, exist_ok=True)
    for item in (constants.GRUB_LIB_DIR / "x86_64-efi").iterdir():
        if item.is_file():
            shutil.copy2(item, efi_src / item.name)

    boot_efi = iso_root / "efi" / "boot"
    boot_efi.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_efi_boot_command(efi_src, boot_efi / "bootx64.efi"), check=True)

    # bootx64.efi only embeds enough to bootstrap into normal mode -- the
    # rest of grub's modules (normal.mod, filesystem drivers, etc.) are
    # loaded at runtime from $prefix/x86_64-efi/*.mod, where $prefix is
    # /boot/grub (baked in by build_efi_boot_command's -p flag). Unlike
    # prepare_bios_boot(), which copies i386-pc's modules straight onto
    # the ISO tree, this only had them in the workdir staging copy
    # grub-mkimage read from -- so they need to actually exist on the ISO
    # too, or GRUB drops to rescue mode looking for normal.mod.
    grub_efi_dest = iso_root / "boot" / "grub" / "x86_64-efi"
    grub_efi_dest.mkdir(parents=True, exist_ok=True)
    for item in efi_src.iterdir():
        if item.is_file():
            shutil.copy2(item, grub_efi_dest / item.name)

    _build_fat_image(iso_root / "efi.img", boot_efi / "bootx64.efi", "efi/boot/bootx64.efi", efi_img_size)


def build_xorriso_command(iso_root: Path, dest: Path, volid: str) -> list[str]:
    return [
        "xorriso", "-as", "mkisofs",
        "--protective-msdos-label",
        "-volid", volid,
        "-appid", "Mabox Linux Live/Rescue",
        "-publisher", "Mabox Linux <https://maboxlinux.org>",
        "-preparer", "Prepared by mabox-snapshot",
        "-r", "-graft-points", "-no-pad",
        "--sort-weight", "0", "/",
        "--sort-weight", "1", "/boot",
        "--grub2-mbr", str(iso_root / "boot" / "grub" / "i386-pc" / "boot_hybrid.img"),
        "-iso_mbr_part_type", "0x00",
        "-partition_offset", "16",
        "-b", "boot/grub/i386-pc/eltorito.img",
        "-c", "boot.catalog",
        "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table", "--grub2-boot-info",
        "-eltorito-alt-boot",
        "-append_partition", "2", "0xef", str(iso_root / "efi.img"),
        "-e", "--interval:appended_partition_2:all::",
        "-no-emul-boot",
        "-full-iso9660-filenames",
        "-iso-level", "3", "-rock", "-joliet",
        "-o", str(dest),
        f"{iso_root}/",
    ]


def assemble(iso_root: Path, dest: Path, volid: str = constants.ISO_VOLID) -> None:
    (iso_root / ".miso").touch()
    subprocess.run(build_xorriso_command(iso_root, dest, volid), check=True)


def write_checksum(dest: Path) -> Path:
    """Writes dest's sha256 as <dest>.sha256, in standard `sha256sum`
    output format so `sha256sum -c` verifies it from the same directory."""
    digest = hashlib.sha256()
    with dest.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum_path = dest.with_name(dest.name + ".sha256")
    checksum_path.write_text(f"{digest.hexdigest()}  {dest.name}\n")
    return checksum_path
