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
