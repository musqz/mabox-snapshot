from pathlib import Path

from mabox_snapshot import calamares, constants


def test_load_branding_returns_none_when_no_slides(tmp_path):
    assert calamares.load_branding(tmp_path) is None


def test_load_branding_parses_toml_and_matches_slide_indices(tmp_path):
    (tmp_path / "slide-0.png").write_bytes(b"fake")
    (tmp_path / "slide-2.png").write_bytes(b"fake")
    (tmp_path / "branding.toml").write_text(
        'product_name = "Mabox Linux"\n'
        "radius = 12\n"
        '[slide.0]\nhead = "Welcome"\nbody = "Enjoy Mabox"\n'
    )

    branding = calamares.load_branding(tmp_path)

    assert branding is not None
    assert branding.product_name == "Mabox Linux"
    assert branding.radius == 12
    assert [s.image for s in branding.slides] == ["slide-0.png", "slide-2.png"]
    assert branding.slides[0].head == "Welcome"
    assert branding.slides[1].head == ""  # no [slide.2] section -- graceful default


def test_build_branding_desc_contains_component_and_product_name():
    branding = calamares.BrandingConfig(product_name="Mabox Linux", radius=8, slides=[])
    desc = calamares.build_branding_desc(branding)

    assert "componentName: mabox" in desc
    assert 'productName: "Mabox Linux"' in desc
    assert 'slideshow: "show.qml"' in desc


def test_build_show_qml_embeds_slide_data():
    branding = calamares.BrandingConfig(
        radius=8, slides=[calamares.Slide(image="slide-0.png", head="Hi", body="Body text")]
    )
    qml = calamares.build_show_qml(branding)

    assert '"slide-0.png"' in qml
    assert '"Hi"' in qml
    assert '"Body text"' in qml
    assert "radius: 8" in qml


def test_write_settings_override_repoints_branding_line(tmp_path):
    source = tmp_path / "settings.conf"
    source.write_text("modules-search: [ local ]\nbranding: manjaro\nprompt-install: false\n")

    overlay_dir = tmp_path / "overlay"
    calamares.write_settings_override(overlay_dir, source)

    result = (overlay_dir / "etc/calamares/settings.conf").read_text()
    assert "branding: mabox" in result
    assert "prompt-install: false" in result  # rest of the file untouched


def test_write_branding_copies_slide_images_and_writes_desc(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "slide-0.png").write_bytes(b"fake-png")

    branding = calamares.BrandingConfig(slides=[calamares.Slide(image="slide-0.png", head="Hi")])
    overlay_dir = tmp_path / "overlay"
    calamares.write_branding(overlay_dir, branding, images_dir)

    branding_dir = overlay_dir / "etc/calamares/branding/mabox"
    assert (branding_dir / "slide-0.png").read_bytes() == b"fake-png"
    assert (branding_dir / "branding.desc").exists()
    assert (branding_dir / "show.qml").exists()


def test_build_calamares_branding_returns_false_when_unconfigured(tmp_path):
    overlay_dir = tmp_path / "overlay"
    applied = calamares.build_calamares_branding(overlay_dir, tmp_path / "no-images")
    assert applied is False
    assert not (overlay_dir / "etc/calamares").exists()


def test_build_unpackfs_conf_one_entry_per_layer():
    conf = calamares.build_unpackfs_conf(["rootfs"], basedir="mabox", arch="x86_64")
    assert conf.count("- source:") == 1
    assert '"/run/miso/bootmnt/mabox/x86_64/rootfs.sfs"' in conf
    assert 'sourcefs: "squashfs"' in conf


def test_build_unpackfs_conf_reset_mode_lists_both_layers_in_order():
    conf = calamares.build_unpackfs_conf(["rootfs", "desktopfs"])
    assert conf.index("rootfs.sfs") < conf.index("desktopfs.sfs")


def test_build_unpackfs_conf_encrypt_sources_rootfs_from_live_luks_mount():
    conf = calamares.build_unpackfs_conf(["rootfs"], encrypt=True)
    assert 'sourcefs: "file"' in conf
    assert constants.MISO_LUKS_LIVE_ROOTFS_MOUNT in conf
    assert 'sourcefs: "squashfs"' not in conf
    assert "rootfs.sfs" not in conf  # not an on-media squashfs reference


def test_build_unpackfs_conf_encrypt_false_is_unaffected():
    conf = calamares.build_unpackfs_conf(["rootfs"], encrypt=False)
    assert 'sourcefs: "squashfs"' in conf
    assert constants.MISO_LUKS_LIVE_ROOTFS_MOUNT not in conf


def test_build_unpackfs_conf_encrypt_only_affects_rootfs_layer():
    conf = calamares.build_unpackfs_conf(["rootfs", "desktopfs"], encrypt=True)
    assert conf.count('sourcefs: "file"') == 1
    assert conf.count('sourcefs: "squashfs"') == 1
    assert "desktopfs.sfs" in conf


def test_live_source_unit_remounts_at_the_constant_path():
    # Regression tripwire: the systemd unit that remounts the already-
    # unlocked dm-crypt device (see constants.MISO_LUKS_LIVE_ROOTFS_MOUNT's
    # docstring for why it exists -- the boot hook's own mount doesn't
    # survive switch_root) must actually mount at the same path this
    # constant says it does, so the Python side and the shipped unit file
    # can't silently drift apart.
    unit_text = Path(__file__).parents[2].joinpath(
        "systemd/system/mabox-snapshot-live-source.service"
    ).read_text()
    assert constants.MISO_LUKS_LIVE_ROOTFS_MOUNT in unit_text
    assert f"ConditionPathExists=/dev/mapper/{constants.ISO_LUKS_MAPPER_NAME}" in unit_text
    assert f"mount -o ro /dev/mapper/{constants.ISO_LUKS_MAPPER_NAME}" in unit_text


def test_unpackfs_pseudo_specs_declares_parent_dirs_before_the_file():
    specs = calamares.unpackfs_pseudo_specs("/work/unpackfs.conf")
    assert specs[0] == "etc/calamares d 755 0 0"
    assert specs[1] == "etc/calamares/modules d 755 0 0"
    assert specs[2].startswith(f"{calamares.UNPACKFS_CONF_PATH} f 644 0 0 cat ")
    assert specs[2].endswith("/work/unpackfs.conf")


def test_unpackfs_pseudo_specs_quotes_a_path_with_spaces():
    specs = calamares.unpackfs_pseudo_specs("/work dir/unpackfs.conf")
    assert "'/work dir/unpackfs.conf'" in specs[2]
