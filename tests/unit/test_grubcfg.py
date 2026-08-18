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


def test_build_splash_command_crops_to_fill_full_canvas_edge_to_edge():
    cmd = grubcfg.build_splash_command(
        Path("/src/wallpaper.jpg"), Path("/dst/splash.png"), "#175B8E", size="1920x1080", fraction=0.18
    )
    assert "1920x1080^" in cmd
    assert "1920x1080" in cmd  # -extent target -- no shrinking, no padding
    assert "-bordercolor" not in cmd
    assert "-border" not in cmd


def test_build_splash_command_composites_top_and_bottom_gradients():
    cmd = grubcfg.build_splash_command(
        Path("/src/wallpaper.jpg"), Path("/dst/splash.png"), "#175B8E", size="1920x1080", fraction=0.18
    )
    assert "gradient:#175B8E-none" in cmd  # top: opaque at the edge, fading inward
    assert "gradient:none-#175B8E" in cmd  # bottom: fading inward, opaque at the edge
    assert "1920x194" in cmd  # round(1080 * 0.18)
    assert cmd.count("north") == 1
    assert cmd.count("south") == 1


def test_overlay_height_px_scales_with_canvas_height():
    assert grubcfg.overlay_height_px("1920x1080", 0.18) == 194
    assert grubcfg.overlay_height_px("1000x1000", 0.1) == 100


def test_darkest_color_picks_luma_darkest_and_formats_as_hex():
    palette = [(212, 217, 220), (23, 91, 142), (140, 133, 113)]
    assert grubcfg.darkest_color(palette) == "#175B8E"


def test_darkest_color_rejects_empty_palette():
    with pytest.raises(ValueError):
        grubcfg.darkest_color([])
