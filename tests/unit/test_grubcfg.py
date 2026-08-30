from pathlib import Path

import pytest

from mabox_snapshot import grubcfg


def test_build_grub_cfg_one_entry_per_kernel_plus_safe_graphics():
    cfg = grubcfg.build_grub_cfg(["linux612", "linux618"], misolabel="TESTLABEL")

    # two kernels + one appended safe-graphics entry
    assert cfg.count("menuentry") == 3
    assert "linux /boot/vmlinuz-linux612 misobasedir=mabox misolabel=TESTLABEL quiet" in cfg
    assert "initrd /boot/initramfs-linux618.img" in cfg


def test_build_grub_cfg_appends_safe_graphics_entry_last():
    cfg = grubcfg.build_grub_cfg(["linux618", "linux612"], misolabel="TESTLABEL")

    assert cfg.count("safe graphics (nomodeset)") == 1
    # uses the first (newest) kernel, drops `quiet`, adds `nomodeset`
    assert "linux /boot/vmlinuz-linux618 misobasedir=mabox misolabel=TESTLABEL nomodeset" in cfg
    assert cfg.rfind("nomodeset") > cfg.rfind('"Mabox Linux (live) -- linux612"')


def test_build_grub_cfg_default_entry_is_not_the_safe_graphics_one():
    cfg = grubcfg.build_grub_cfg(["linux618"])
    assert "set default=0" in cfg
    assert cfg.index('"Mabox Linux (live) -- linux618"') < cfg.index("nomodeset")


def test_build_grub_cfg_requires_at_least_one_kernel():
    with pytest.raises(ValueError):
        grubcfg.build_grub_cfg([])


def test_build_grub_cfg_omits_memtest_by_default():
    cfg = grubcfg.build_grub_cfg(["linux618", "linux612"])
    assert "memtest" not in cfg
    # two kernels + one safe-graphics entry, nothing more
    assert cfg.count("menuentry") == 3


def test_build_grub_cfg_bios_memtest_entry_is_pc_guarded():
    cfg = grubcfg.build_grub_cfg(["linux618"], memtest_bios=True)
    assert 'menuentry "Mabox Linux (live) -- memory test (memtest86+)"' in cfg
    assert 'if [ "${grub_platform}" = "pc" ]; then' in cfg
    assert "linux16 /boot/memtest86+/memtest.bin" in cfg
    assert "chainloader" not in cfg


def test_build_grub_cfg_efi_memtest_entry_is_efi_guarded():
    cfg = grubcfg.build_grub_cfg(["linux618"], memtest_efi=True)
    assert 'if [ "${grub_platform}" = "efi" ]; then' in cfg
    assert "chainloader /boot/memtest86+/memtest.efi" in cfg
    assert "linux16" not in cfg


def test_build_grub_cfg_both_memtest_images_emit_two_guarded_blocks():
    cfg = grubcfg.build_grub_cfg(["linux618"], memtest_bios=True, memtest_efi=True)
    assert cfg.count('menuentry "Mabox Linux (live) -- memory test (memtest86+)"') == 2
    assert cfg.count("if [ ") == 2
    assert cfg.count("}\nfi\n") == 2
    # memtest is self-contained -- no live-rootfs cmdline on those entries
    assert "misobasedir" not in cfg.split("memory test", 1)[1]


def test_build_grub_cfg_memtest_entries_come_after_safe_graphics():
    cfg = grubcfg.build_grub_cfg(["linux618"], memtest_bios=True, memtest_efi=True)
    assert cfg.rfind("nomodeset") < cfg.find("memtest86+")


def test_build_grub_cfg_omits_background_by_default():
    cfg = grubcfg.build_grub_cfg(["linux618"])
    assert "background_image" not in cfg


def test_build_grub_cfg_includes_background_when_splash_present():
    cfg = grubcfg.build_grub_cfg(["linux618"], has_splash=True)
    assert "insmod png" in cfg
    assert "background_image /boot/grub/splash.png" in cfg


def test_build_grub_cfg_loads_a_unicode_font_before_gfxterm_output():
    """Without this, gfxterm's default bordered-menu style falls back to a
    minimal font lacking glyphs for its own Unicode box-drawing characters,
    rendering as placeholder boxes instead of a clean border -- confirmed
    on a real boot."""
    cfg = grubcfg.build_grub_cfg(["linux618"])
    lines = cfg.splitlines()
    assert "insmod font" in lines
    assert "loadfont /boot/grub/unicode.pf2" in lines
    assert lines.index("loadfont /boot/grub/unicode.pf2") < lines.index("terminal_output gfxterm")


def test_build_splash_command_uses_magick_not_convert():
    cmd = grubcfg.build_splash_command(Path("/src/wallpaper.jpg"), Path("/dst/splash.png"))
    assert cmd[0] == "magick"
    assert "convert" not in cmd
    assert str(Path("/src/wallpaper.jpg")) in cmd
    assert str(Path("/dst/splash.png")) in cmd


def test_build_splash_command_crops_to_fill_full_canvas_edge_to_edge():
    cmd = grubcfg.build_splash_command(Path("/src/wallpaper.jpg"), Path("/dst/splash.png"), size="1920x1080")
    assert "1920x1080^" in cmd
    assert "1920x1080" in cmd  # -extent target -- no shrinking, no padding
    assert "-bordercolor" not in cmd
    assert "-border" not in cmd
    assert "-composite" not in cmd  # plain resize/crop, no gradient overlay
