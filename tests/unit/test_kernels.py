from mabox_snapshot import kernels


def _write_preset(preset_dir, name, kver_path, image_path, kver_exists=True):
    preset_dir.mkdir(parents=True, exist_ok=True)
    (preset_dir / f"{name}.preset").write_text(
        f'ALL_kver="{kver_path}"\ndefault_image="{image_path}"\n'
    )
    if kver_exists:
        kver_path.parent.mkdir(parents=True, exist_ok=True)
        kver_path.write_bytes(b"fake-vmlinuz")


def test_detects_multiple_installed_kernels(tmp_path):
    preset_dir = tmp_path / "mkinitcpio.d"
    boot = tmp_path / "boot"
    _write_preset(preset_dir, "linux612", boot / "vmlinuz-6.12-x86_64", boot / "initramfs-6.12-x86_64.img")
    _write_preset(preset_dir, "linux618", boot / "vmlinuz-6.18-x86_64", boot / "initramfs-6.18-x86_64.img")

    result = kernels.detect_installed_kernels(preset_dir)

    assert [k.name for k in result] == ["linux612", "linux618"]
    assert result[1].vmlinuz == boot / "vmlinuz-6.18-x86_64"


def test_skips_stale_preset_without_vmlinuz(tmp_path):
    preset_dir = tmp_path / "mkinitcpio.d"
    boot = tmp_path / "boot"
    _write_preset(preset_dir, "linux612", boot / "vmlinuz-6.12-x86_64", boot / "initramfs-6.12-x86_64.img")
    _write_preset(preset_dir, "linux-old", boot / "vmlinuz-old", boot / "initramfs-old.img", kver_exists=False)

    result = kernels.detect_installed_kernels(preset_dir)

    assert [k.name for k in result] == ["linux612"]


def test_missing_preset_dir_returns_empty(tmp_path):
    assert kernels.detect_installed_kernels(tmp_path / "does-not-exist") == []


def test_find_kernel_by_name(tmp_path):
    preset_dir = tmp_path / "mkinitcpio.d"
    boot = tmp_path / "boot"
    _write_preset(preset_dir, "linux618", boot / "vmlinuz-6.18-x86_64", boot / "initramfs-6.18-x86_64.img")

    found = kernels.find_kernel("linux618", preset_dir)
    missing = kernels.find_kernel("linux612", preset_dir)

    assert found is not None and found.name == "linux618"
    assert missing is None
