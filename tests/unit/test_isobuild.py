import hashlib
import subprocess
from pathlib import Path

import pytest

from mabox_snapshot import isobuild


def test_build_mkinitcpio_command():
    cmd = isobuild.build_mkinitcpio_command("6.18.44-1-MANJARO", Path("/tmp/conf"), Path("/tmp/out.img"))
    assert cmd == ["mkinitcpio", "-k", "6.18.44-1-MANJARO", "-c", "/tmp/conf", "-g", "/tmp/out.img"]


def test_write_mkinitcpio_conf_contains_miso_hooks(tmp_path):
    dest = isobuild.write_mkinitcpio_conf(tmp_path / "mkinitcpio-miso.conf")
    text = dest.read_text()
    assert "miso" in text
    assert "HOOKS=(" in text
    assert "MODULES=(loop dm-snapshot)" in text


def test_build_mtools_mmd_command_prefixes_each_dir_with_the_image_root():
    cmd = isobuild.build_mtools_mmd_command(Path("/work/efi.img"), ["efi", "efi/boot"])
    assert cmd == ["mmd", "-i", "/work/efi.img", "::efi", "::efi/boot"]


def test_build_mtools_mcopy_command_targets_an_image_internal_path():
    cmd = isobuild.build_mtools_mcopy_command(
        Path("/work/efi.img"), Path("/work/bootx64.efi"), "efi/boot/bootx64.efi"
    )
    assert cmd == ["mcopy", "-i", "/work/efi.img", "/work/bootx64.efi", "::efi/boot/bootx64.efi"]


def test_build_fat_image_fills_the_image_with_mtools_not_a_loop_mount(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        isobuild.subprocess,
        "run",
        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
    )

    src = tmp_path / "bootx64.efi"
    src.write_bytes(b"efi")
    isobuild._build_fat_image(tmp_path / "efi.img", src, "efi/boot/bootx64.efi", 4 * 1024 * 1024)

    programs = [c[0] for c in calls]
    assert programs == ["mkfs.fat", "mmd", "mcopy"]
    assert "mount" not in programs and "umount" not in programs
    assert (tmp_path / "efi.img").stat().st_size == 4 * 1024 * 1024
    assert [c for c in calls if c[0] == "mmd"][0][-2:] == ["::efi", "::efi/boot"]
    assert [c for c in calls if c[0] == "mcopy"][0][-1] == "::efi/boot/bootx64.efi"


def test_build_bios_boot_command():
    cmd = isobuild.build_bios_boot_command(Path("/work/i386-pc"))
    assert cmd[:2] == ["grub-mkimage", "-d"]
    assert "biosdisk" in cmd and "iso9660" in cmd


def test_build_efi_boot_command_omits_biosdisk():
    cmd = isobuild.build_efi_boot_command(Path("/work/x86_64-efi"), Path("/work/bootx64.efi"))
    assert "-O" in cmd and "x86_64-efi" in cmd
    assert "biosdisk" not in cmd
    assert "iso9660" in cmd


def test_build_xorriso_command_references_boot_files():
    cmd = isobuild.build_xorriso_command(Path("/iso"), Path("/out/mabox.iso"), "MYVOLID")

    assert "-volid" in cmd and "MYVOLID" in cmd
    assert str(Path("/iso/boot/grub/i386-pc/boot_hybrid.img")) in cmd
    assert str(Path("/iso/efi.img")) in cmd
    assert cmd[-1] == "/iso/"
    assert cmd[cmd.index("-o") + 1] == "/out/mabox.iso"


def test_build_xorriso_command_gives_the_iso_content_its_own_real_partition():
    # Load-bearing for the live-boot device-resolution fix: -partition_offset
    # is what makes the ISO9660 content mountable from a real MBR partition
    # (in addition to the whole-disk view), which is what lets
    # miso_boot's/miso_luks's fixed _find_dev_by_path() resolve to a
    # partition instead of the whole disk at boot. -iso_mbr_part_type must
    # be non-zero (0x17, matching syslinux isohybrid's own default) -- 0x00
    # is the literal MBR "unused slot" marker, so parted's mkpart (used by
    # mabox-persistence-usb to append MABOX_PERSIST) would treat this slot
    # as free and silently overwrite it instead of skipping past it.
    cmd = isobuild.build_xorriso_command(Path("/iso"), Path("/out/mabox.iso"), "MYVOLID")

    assert cmd[cmd.index("-partition_offset") + 1] == "16"
    assert cmd[cmd.index("-iso_mbr_part_type") + 1] == "0x17"


def test_check_miso_hooks_installed_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="manjaro-tools-iso-git"):
        isobuild.check_miso_hooks_installed(["miso"], [tmp_path])


def test_check_miso_hooks_installed_lists_each_missing_hook(tmp_path):
    with pytest.raises(FileNotFoundError, match="miso_shutdown, miso_kms"):
        isobuild.check_miso_hooks_installed(["miso_shutdown", "miso_kms"], [tmp_path])


def test_check_miso_hooks_installed_passes_when_present_in_any_search_dir(tmp_path):
    first_dir = tmp_path / "etc-initcpio-hooks"
    second_dir = tmp_path / "usr-lib-initcpio-hooks"
    first_dir.mkdir()
    second_dir.mkdir()
    (first_dir / "miso").write_text("# hook")
    (second_dir / "miso_kms").write_text("# hook")

    isobuild.check_miso_hooks_installed(["miso", "miso_kms"], [first_dir, second_dir])  # must not raise


def test_check_miso_hook_binaries_installed_raises_when_missing(monkeypatch):
    monkeypatch.setattr(isobuild.shutil, "which", lambda _b: None)
    with pytest.raises(FileNotFoundError, match="nbd and/or curl"):
        isobuild.check_miso_hook_binaries_installed(["nbd-client"])


def test_check_miso_hook_binaries_installed_lists_each_missing_binary(monkeypatch):
    monkeypatch.setattr(isobuild.shutil, "which", lambda _b: None)
    with pytest.raises(FileNotFoundError, match="curl, nbd-client"):
        isobuild.check_miso_hook_binaries_installed(["curl", "nbd-client"])


def test_check_miso_hook_binaries_installed_passes_when_present(monkeypatch):
    monkeypatch.setattr(isobuild.shutil, "which", lambda b: f"/usr/bin/{b}")
    isobuild.check_miso_hook_binaries_installed(["curl", "nbd-client"])  # must not raise


def test_write_persist_hook_marker_writes_version_under_miso_basedir(tmp_path):
    dest = isobuild.write_persist_hook_marker(tmp_path, version=1, relpath=Path("mabox/.persist-hook-version"))

    assert dest == tmp_path / "mabox" / ".persist-hook-version"
    assert dest.read_text() == "1\n"


def test_check_miso_persist_hook_installed_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="persistence boot hook"):
        isobuild.check_miso_persist_hook_installed(tmp_path / "miso_persist")


def test_check_miso_persist_hook_installed_passes_when_present(tmp_path):
    hook_path = tmp_path / "miso_persist"
    hook_path.write_text("# hook")

    isobuild.check_miso_persist_hook_installed(hook_path)  # must not raise


def test_check_miso_boot_hook_installed_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="boot hook"):
        isobuild.check_miso_boot_hook_installed(tmp_path / "miso_boot")


def test_check_miso_boot_hook_installed_passes_when_present(tmp_path):
    hook_path = tmp_path / "miso_boot"
    hook_path.write_text("# hook")

    isobuild.check_miso_boot_hook_installed(hook_path)  # must not raise


def test_write_checksum_matches_sha256sum_format(tmp_path):
    iso = tmp_path / "mabox-reset-20260823.iso"
    iso.write_bytes(b"fake iso contents")

    checksum_path = isobuild.write_checksum(iso)

    assert checksum_path == tmp_path / "mabox-reset-20260823.iso.sha256"
    expected = hashlib.sha256(iso.read_bytes()).hexdigest()
    assert checksum_path.read_text() == f"{expected}  {iso.name}\n"
