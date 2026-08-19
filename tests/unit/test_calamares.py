import pytest

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


SETTINGS_CONF_FIXTURE = (
    "modules-search: [ local ]\nbranding: manjaro\nprompt-install: false\n"
    "sequence:\n- show:\n  - users\n- exec:\n  - unpackfs\n  - users\n  - services\n"
)


def test_write_settings_override_repoints_branding_line(tmp_path):
    source = tmp_path / "settings.conf"
    source.write_text(SETTINGS_CONF_FIXTURE)

    overlay_dir = tmp_path / "overlay"
    calamares.write_settings_override(overlay_dir, source, repoint_branding=True)

    result = (overlay_dir / "etc/calamares/settings.conf").read_text()
    assert "branding: mabox" in result
    assert "prompt-install: false" in result  # rest of the file untouched


def test_write_settings_override_default_does_not_repoint_branding(tmp_path):
    source = tmp_path / "settings.conf"
    source.write_text(SETTINGS_CONF_FIXTURE)

    overlay_dir = tmp_path / "overlay"
    calamares.write_settings_override(overlay_dir, source)

    result = (overlay_dir / "etc/calamares/settings.conf").read_text()
    assert "branding: manjaro" in result


def test_write_settings_override_always_inserts_removeuser(tmp_path):
    source = tmp_path / "settings.conf"
    source.write_text(SETTINGS_CONF_FIXTURE)

    overlay_dir = tmp_path / "overlay"
    calamares.write_settings_override(overlay_dir, source)

    result = (overlay_dir / "etc/calamares/settings.conf").read_text()
    lines = result.splitlines()
    users_indices = [i for i, line in enumerate(lines) if line == "  - users"]
    assert len(users_indices) == 2
    assert lines[users_indices[-1] + 1] == "  - removeuser"


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


def test_build_shellprocess_remount_conf_contains_mount_point_and_mapper():
    conf = calamares.build_shellprocess_remount_conf(mount_point="/run/mabox-snapshot/live-source", mapper_name="mabox_rootfs")
    assert "dontChroot: true" in conf
    assert "mkdir -p /run/mabox-snapshot/live-source" in conf
    assert "mountpoint -q /run/mabox-snapshot/live-source" in conf
    assert "mount -o ro /dev/mapper/mabox_rootfs /run/mabox-snapshot/live-source" in conf


def test_build_shellprocess_remount_conf_defaults_match_constants():
    conf = calamares.build_shellprocess_remount_conf()
    assert constants.MISO_LUKS_LIVE_ROOTFS_MOUNT in conf
    assert constants.ISO_LUKS_MAPPER_NAME in conf


def test_insert_live_source_job_inserts_before_unpackfs_preserving_indent():
    settings = "sequence:\n- exec:\n  - partition\n  - mount\n  - unpackfs\n  - machineid\n"
    result = calamares.insert_live_source_job(settings)
    lines = result.splitlines()
    assert f"  - {calamares.SHELLPROCESS_INSTANCE}" in lines
    unpackfs_index = lines.index("  - unpackfs")
    assert lines[unpackfs_index - 1] == f"  - {calamares.SHELLPROCESS_INSTANCE}"


def test_insert_live_source_job_raises_when_unpackfs_missing():
    with pytest.raises(ValueError):
        calamares.insert_live_source_job("sequence:\n- exec:\n  - partition\n  - mount\n")


def test_unpackfs_pseudo_specs_declares_parent_dirs_before_the_file():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf"
    )
    assert specs[0] == "etc/calamares d 755 0 0"
    assert specs[1] == "etc/calamares/modules d 755 0 0"
    assert specs[2].startswith(f"{calamares.UNPACKFS_CONF_PATH} f 644 0 0 cat ")
    assert specs[2].endswith("/work/unpackfs.conf")


def test_unpackfs_pseudo_specs_quotes_a_path_with_spaces():
    specs = calamares.unpackfs_pseudo_specs(
        "/work dir/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf"
    )
    assert "'/work dir/unpackfs.conf'" in specs[2]


def test_unpackfs_pseudo_specs_always_injects_initcpio_override():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf"
    )
    assert len(specs) == 5
    initcpio_spec = next(s for s in specs if s.startswith(calamares.INITCPIO_CONF_TARGET_PATH))
    assert initcpio_spec.endswith("/work/initcpio-override.conf")


def test_unpackfs_pseudo_specs_always_injects_services_override():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf"
    )
    assert len(specs) == 5
    services_spec = next(s for s in specs if s.startswith(calamares.SERVICES_CONF_TARGET_PATH))
    assert services_spec.endswith("/work/services-override.conf")


def test_unpackfs_pseudo_specs_encrypt_true_injects_settings_and_shellprocess():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf",
        "/work/initcpio-override.conf",
        "/work/services-override.conf",
        encrypt=True,
        settings_conf_path="/work/settings-encrypt.conf",
        shellprocess_conf_path="/work/shellprocess-remount.conf",
    )
    assert len(specs) == 7
    settings_spec = next(s for s in specs if s.startswith(calamares.SETTINGS_CONF_TARGET_PATH))
    assert settings_spec.endswith("/work/settings-encrypt.conf")
    shellprocess_spec = next(s for s in specs if s.startswith(calamares.SHELLPROCESS_CONF_TARGET_PATH))
    assert shellprocess_spec.endswith("/work/shellprocess-remount.conf")


def test_initcpio_conf_override_regenerates_every_preset():
    assert "kernel: all" in calamares.INITCPIO_CONF_OVERRIDE


def test_services_conf_override_drops_graphical_unit_keeps_networkmanager_mandatory():
    assert 'name: "graphical"' not in calamares.SERVICES_CONF_OVERRIDE
    assert 'name: "NetworkManager"' in calamares.SERVICES_CONF_OVERRIDE
    assert "mandatory: true" in calamares.SERVICES_CONF_OVERRIDE
    assert 'name: "pacman-init"' in calamares.SERVICES_CONF_OVERRIDE
    assert 'action: "mask"' in calamares.SERVICES_CONF_OVERRIDE


def test_insert_removeuser_job_inserts_after_the_exec_phase_users_line():
    settings = "sequence:\n- show:\n  - users\n- exec:\n  - unpackfs\n  - users\n  - displaymanager\n"
    result = calamares.insert_removeuser_job(settings)
    lines = result.splitlines()
    users_indices = [i for i, line in enumerate(lines) if line == "  - users"]
    assert len(users_indices) == 2  # show-phase 'users' is untouched, only the exec one gets removeuser after it
    assert lines[users_indices[-1] + 1] == "  - removeuser"


def test_insert_removeuser_job_raises_when_users_missing():
    with pytest.raises(ValueError):
        calamares.insert_removeuser_job("sequence:\n- exec:\n  - unpackfs\n")


def test_removeuser_conf_override_targets_demo_account():
    assert calamares.REMOVEUSER_CONF_OVERRIDE == f"username: {constants.DEMO_USERNAME}\n"


def test_write_removeuser_override_writes_demo_username(tmp_path):
    overlay_dir = tmp_path / "overlay"
    calamares.write_removeuser_override(overlay_dir)

    result = (overlay_dir / calamares.REMOVEUSER_CONF_TARGET_PATH).read_text()
    assert result == f"username: {constants.DEMO_USERNAME}\n"
