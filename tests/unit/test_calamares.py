import pytest

from mabox_snapshot import calamares, constants


SETTINGS_CONF_FIXTURE = (
    "modules-search: [ local ]\nbranding: manjaro\nprompt-install: false\n"
    "sequence:\n- show:\n  - users\n- exec:\n  - unpackfs\n  - users\n  - services\n"
)


def test_write_settings_override_repoints_branding_line(tmp_path):
    source = tmp_path / "settings.conf"
    source.write_text(SETTINGS_CONF_FIXTURE)

    overlay_dir = tmp_path / "overlay"
    calamares.write_settings_override(overlay_dir, source)

    result = (overlay_dir / "etc/calamares/settings.conf").read_text()
    assert "branding: mabox" in result
    assert "prompt-install: false" in result  # rest of the file untouched


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


def test_write_branding_copies_every_file_from_src_dir(tmp_path):
    src_dir = tmp_path / "branding-src"
    src_dir.mkdir()
    (src_dir / "branding.desc").write_text("componentName: mabox\n")
    (src_dir / "show.qml").write_text("Presentation {}\n")
    (src_dir / "1.png").write_bytes(b"fake-png")

    overlay_dir = tmp_path / "overlay"
    calamares.write_branding(overlay_dir, src_dir)

    branding_dir = overlay_dir / "etc/calamares/branding/mabox"
    assert (branding_dir / "branding.desc").read_text() == "componentName: mabox\n"
    assert (branding_dir / "show.qml").read_text() == "Presentation {}\n"
    assert (branding_dir / "1.png").read_bytes() == b"fake-png"


def test_write_branding_ignores_subdirectories(tmp_path):
    """src_dir.iterdir()'s is_file() guard -- a stray subdirectory (there
    shouldn't be one, but nothing enforces it) must not raise or get
    copied wholesale."""
    src_dir = tmp_path / "branding-src"
    (src_dir / "nested").mkdir(parents=True)
    (src_dir / "nested" / "unused.txt").write_text("x")
    (src_dir / "1.png").write_bytes(b"fake-png")

    overlay_dir = tmp_path / "overlay"
    calamares.write_branding(overlay_dir, src_dir)

    branding_dir = overlay_dir / "etc/calamares/branding/mabox"
    assert (branding_dir / "1.png").exists()
    assert not (branding_dir / "nested").exists()


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


def test_build_shellprocess_cleanup_conf_contains_mount_point_and_mapper():
    conf = calamares.build_shellprocess_cleanup_conf(mount_point="/run/mabox-snapshot/live-source", mapper_name="mabox_rootfs")
    assert "dontChroot: true" in conf
    assert "-umount /run/mabox-snapshot/live-source" in conf
    assert "-cryptsetup close mabox_rootfs" in conf


def test_build_shellprocess_cleanup_conf_defaults_match_constants():
    conf = calamares.build_shellprocess_cleanup_conf()
    assert constants.MISO_LUKS_LIVE_ROOTFS_MOUNT in conf
    assert constants.ISO_LUKS_MAPPER_NAME in conf


def test_insert_live_source_job_inserts_before_unpackfs_preserving_indent():
    settings = "sequence:\n- exec:\n  - partition\n  - mount\n  - unpackfs\n  - machineid\n"
    result = calamares.insert_live_source_job(settings)
    lines = result.splitlines()
    assert f"  - {calamares.SHELLPROCESS_INSTANCE}" in lines
    unpackfs_index = lines.index("  - unpackfs")
    assert lines[unpackfs_index - 1] == f"  - {calamares.SHELLPROCESS_INSTANCE}"


def test_insert_live_source_job_inserts_cleanup_job_after_unpackfs_preserving_indent():
    settings = "sequence:\n- exec:\n  - partition\n  - mount\n  - unpackfs\n  - machineid\n"
    result = calamares.insert_live_source_job(settings)
    lines = result.splitlines()
    assert f"  - {calamares.SHELLPROCESS_CLEANUP_INSTANCE}" in lines
    unpackfs_index = lines.index("  - unpackfs")
    assert lines[unpackfs_index + 1] == f"  - {calamares.SHELLPROCESS_CLEANUP_INSTANCE}"


def test_insert_live_source_job_raises_when_unpackfs_missing():
    with pytest.raises(ValueError):
        calamares.insert_live_source_job("sequence:\n- exec:\n  - partition\n  - mount\n")


def test_insert_live_source_job_declares_shellprocess_instance():
    settings = "sequence:\n- exec:\n  - partition\n  - mount\n  - unpackfs\n  - machineid\n"
    result = calamares.insert_live_source_job(settings)
    lines = result.splitlines()
    assert "instances:" in lines
    assert f"  - id: {calamares.SHELLPROCESS_INSTANCE_ID}" in lines
    assert "    module: shellprocess" in lines
    assert f"    config: {calamares.SHELLPROCESS_INSTANCE}.conf" in lines
    # the instances: block must come before sequence: (top-level keys),
    # not get spliced into the middle of the exec list
    assert lines.index("instances:") < lines.index("sequence:")


def test_insert_live_source_job_declares_cleanup_shellprocess_instance():
    settings = "sequence:\n- exec:\n  - partition\n  - mount\n  - unpackfs\n  - machineid\n"
    result = calamares.insert_live_source_job(settings)
    lines = result.splitlines()
    assert f"  - id: {calamares.SHELLPROCESS_CLEANUP_INSTANCE_ID}" in lines
    assert f"    config: {calamares.SHELLPROCESS_CLEANUP_INSTANCE}.conf" in lines
    assert lines.index("instances:") < lines.index("sequence:")


def test_insert_live_source_job_raises_when_sequence_key_missing():
    with pytest.raises(ValueError):
        calamares.insert_live_source_job("exec:\n  - unpackfs\n")


def test_remove_users_step_removes_both_show_and_exec_occurrences():
    settings = (
        "sequence:\n"
        "- show:\n"
        "  - welcome\n"
        "  - users\n"
        "  - summary\n"
        "- exec:\n"
        "  - unpackfs\n"
        "  - users\n"
        "  - displaymanager\n"
    )
    result = calamares.remove_users_step(settings)
    assert "- users" not in result
    # everything else survives untouched
    assert "- welcome" in result
    assert "- summary" in result
    assert "- unpackfs" in result
    assert "- displaymanager" in result


def test_remove_users_step_raises_when_users_missing():
    with pytest.raises(ValueError):
        calamares.remove_users_step("sequence:\n- exec:\n  - unpackfs\n")


def test_remove_users_step_does_not_match_a_users_line_with_trailing_content():
    """Regression guard for the anchor: a line that merely starts with
    '- users' but has real content after it (e.g. a future instance-style
    '- users: something') is not a bare account-creation step and must be
    left alone -- and since that's the only 'users' text in this fixture,
    remove_users_step() has nothing bare to remove and must raise, not
    silently strip just the '- users' prefix and corrupt the line."""
    with pytest.raises(ValueError):
        calamares.remove_users_step("sequence:\n- exec:\n  - users: something\n  - unpackfs\n")


def test_unpackfs_pseudo_specs_declares_parent_dirs_before_the_file():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf", "/work/grubcfg-override.conf"
    )
    assert specs[0] == "etc/calamares d 755 0 0"
    assert specs[1] == "etc/calamares/modules d 755 0 0"
    assert specs[2].startswith(f"{calamares.UNPACKFS_CONF_PATH} f 644 0 0 cat ")
    assert specs[2].endswith("/work/unpackfs.conf")


def test_unpackfs_pseudo_specs_quotes_a_path_with_spaces():
    specs = calamares.unpackfs_pseudo_specs(
        "/work dir/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf", "/work/grubcfg-override.conf"
    )
    assert "'/work dir/unpackfs.conf'" in specs[2]


def test_unpackfs_pseudo_specs_always_injects_initcpio_override():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf", "/work/grubcfg-override.conf"
    )
    assert len(specs) == 6
    initcpio_spec = next(s for s in specs if s.startswith(calamares.INITCPIO_CONF_TARGET_PATH))
    assert initcpio_spec.endswith("/work/initcpio-override.conf")


def test_unpackfs_pseudo_specs_always_injects_services_override():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf", "/work/grubcfg-override.conf"
    )
    assert len(specs) == 6
    services_spec = next(s for s in specs if s.startswith(calamares.SERVICES_CONF_TARGET_PATH))
    assert services_spec.endswith("/work/services-override.conf")


def test_unpackfs_pseudo_specs_always_injects_grubcfg_override():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf", "/work/initcpio-override.conf", "/work/services-override.conf", "/work/grubcfg-override.conf"
    )
    assert len(specs) == 6
    grubcfg_spec = next(s for s in specs if s.startswith(calamares.GRUBCFG_CONF_TARGET_PATH))
    assert grubcfg_spec.endswith("/work/grubcfg-override.conf")


def test_unpackfs_pseudo_specs_encrypt_true_injects_settings_and_shellprocess():
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf",
        "/work/initcpio-override.conf",
        "/work/services-override.conf",
        "/work/grubcfg-override.conf",
        encrypt=True,
        settings_conf_path="/work/settings-encrypt.conf",
        shellprocess_conf_path="/work/shellprocess-remount.conf",
        shellprocess_cleanup_conf_path="/work/shellprocess-cleanup.conf",
    )
    assert len(specs) == 9
    settings_spec = next(s for s in specs if s.startswith(calamares.SETTINGS_CONF_TARGET_PATH))
    assert settings_spec.endswith("/work/settings-encrypt.conf")
    shellprocess_spec = next(s for s in specs if s.startswith(calamares.SHELLPROCESS_CONF_TARGET_PATH))
    assert shellprocess_spec.endswith("/work/shellprocess-remount.conf")
    cleanup_spec = next(s for s in specs if s.startswith(calamares.SHELLPROCESS_CLEANUP_CONF_TARGET_PATH))
    assert cleanup_spec.endswith("/work/shellprocess-cleanup.conf")


def test_unpackfs_pseudo_specs_settings_conf_injected_without_encrypt():
    """Every preserving-mode build needs its own settings.conf (to remove
    the users step, see remove_users_step()) even when --encrypt isn't
    used at all -- settings_conf_path must not be gated behind encrypt."""
    specs = calamares.unpackfs_pseudo_specs(
        "/work/unpackfs.conf",
        "/work/initcpio-override.conf",
        "/work/services-override.conf",
        "/work/grubcfg-override.conf",
        settings_conf_path="/work/settings-preserving.conf",
    )
    assert len(specs) == 7
    settings_spec = next(s for s in specs if s.startswith(calamares.SETTINGS_CONF_TARGET_PATH))
    assert settings_spec.endswith("/work/settings-preserving.conf")
    assert not any(s.startswith(calamares.SHELLPROCESS_CONF_TARGET_PATH) for s in specs)


def test_grubcfg_conf_override_keeps_existing_distributor():
    assert "keep_distributor: true" in calamares.GRUBCFG_CONF_OVERRIDE


def test_grubcfg_conf_override_preserves_stock_defaults():
    assert 'kernel_params: [ "quiet" ]' in calamares.GRUBCFG_CONF_OVERRIDE
    assert "GRUB_TIMEOUT: 5" in calamares.GRUBCFG_CONF_OVERRIDE
    assert "overwrite: false" in calamares.GRUBCFG_CONF_OVERRIDE


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
