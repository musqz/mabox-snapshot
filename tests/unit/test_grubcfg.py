from pathlib import Path

import pytest

from mabox_snapshot import grubcfg


def test_build_grub_cfg_one_entry_per_kernel():
    cfg = grubcfg.build_grub_cfg(["linux612", "linux618"], misolabel="TESTLABEL")

    assert cfg.count("menuentry") == 2
    assert "linux /boot/vmlinuz-linux612 misobasedir=mabox misolabel=TESTLABEL quiet" in cfg
    assert "initrd /boot/initramfs-linux618.img" in cfg


def test_build_grub_cfg_requires_at_least_one_kernel():
    with pytest.raises(ValueError):
        grubcfg.build_grub_cfg([])


def test_build_grub_cfg_omits_background_by_default():
    cfg = grubcfg.build_grub_cfg(["linux618"])
    assert "background_image" not in cfg


def test_build_grub_cfg_includes_background_when_splash_present():
    cfg = grubcfg.build_grub_cfg(["linux618"], has_splash=True)
    assert "insmod png" in cfg
    assert "background_image /boot/grub/splash.png" in cfg


def test_build_splash_command_uses_magick_not_convert():
    cmd = grubcfg.build_splash_command(Path("/src/wallpaper.jpg"), Path("/dst/splash.png"))
    assert cmd[0] == "magick"
    assert "convert" not in cmd
    assert str(Path("/src/wallpaper.jpg")) in cmd
    assert str(Path("/dst/splash.png")) in cmd
