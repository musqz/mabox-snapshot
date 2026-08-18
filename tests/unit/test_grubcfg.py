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
    cmd = grubcfg.build_splash_command(Path("/src/wallpaper.jpg"), Path("/dst/splash.png"), "#175B8E")
    assert cmd[0] == "magick"
    assert "convert" not in cmd
    assert str(Path("/src/wallpaper.jpg")) in cmd
    assert str(Path("/dst/splash.png")) in cmd


def test_build_splash_command_pads_with_border_color_to_full_canvas():
    cmd = grubcfg.build_splash_command(
        Path("/src/wallpaper.jpg"), Path("/dst/splash.png"), "#175B8E", size="1920x1080", fraction=0.06
    )
    assert "-bordercolor" in cmd
    assert cmd[cmd.index("-bordercolor") + 1] == "#175B8E"
    assert "-border" in cmd
    assert cmd[cmd.index("-border") + 1] == "65"  # round(1080 * 0.06)
    assert "1790x950" in cmd  # inner box: canvas minus border on both sides


def test_border_px_scales_with_shorter_canvas_side():
    assert grubcfg.border_px("1920x1080", 0.06) == 65
    assert grubcfg.border_px("1000x1000", 0.1) == 100


def test_darkest_color_picks_luma_darkest_and_formats_as_hex():
    palette = [(212, 217, 220), (23, 91, 142), (140, 133, 113)]
    assert grubcfg.darkest_color(palette) == "#175B8E"


def test_darkest_color_rejects_empty_palette():
    with pytest.raises(ValueError):
        grubcfg.darkest_color([])
