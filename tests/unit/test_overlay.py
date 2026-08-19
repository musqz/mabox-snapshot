from pathlib import Path

import pytest

from mabox_snapshot import overlay, squashfs


@pytest.fixture(autouse=True)
def _no_real_mounts(monkeypatch, tmp_path):
    """resolve_plan() reads the live host's mount table and override-rules
    file by default (via excludes.detect_foreign_mount_excludes() and
    excludes.OverrideRuleList()) -- point both at paths that don't exist
    so these tests stay hermetic regardless of what's mounted or
    configured on the machine running them."""
    monkeypatch.setattr(overlay.constants, "MOUNTS_FILE", tmp_path / "mounts-not-present")
    monkeypatch.setattr(overlay.constants, "OVERRIDE_RULES_FILE", tmp_path / "overrides-not-present")


def test_resolve_plan_preserving_has_single_rootfs_layer(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("var/log/*\n")

    plan = overlay.resolve_plan("preserving", tmp_path / "work", exclude_list)

    assert plan.overlay_dir is None
    assert [layer.name for layer in plan.layers] == ["rootfs"]
    assert plan.layers[0].source == Path("/")
    assert "var/log/*" in plan.layers[0].exclude_patterns


def test_resolve_plan_rootfs_layer_includes_foreign_mount_excludes(tmp_path, monkeypatch):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 /mount/data_opslag ext4 rw 0 0\n")

    plan = overlay.resolve_plan("preserving", tmp_path / "work", exclude_list, mounts_file=mounts)

    assert "mount/data_opslag/*" in plan.layers[0].exclude_patterns


def test_resolve_plan_deduplicates_across_exclude_sources(tmp_path):
    # Same pattern from two independent sources: the user's own exclude
    # list, and detect_foreign_mount_excludes() deriving it from a real
    # mount at the same path.
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("mount/data_opslag/*\n")
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 /mount/data_opslag ext4 rw 0 0\n")
    workdir = tmp_path / "work"

    plan = overlay.resolve_plan("preserving", workdir, exclude_list, mounts_file=mounts)

    patterns = plan.layers[0].exclude_patterns
    assert patterns.count("mount/data_opslag/*") == 1


def test_resolve_plan_reset_has_two_independent_layers(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")
    workdir = tmp_path / "work"

    plan = overlay.resolve_plan("reset", workdir, exclude_list)

    assert [layer.name for layer in plan.layers] == ["rootfs", "desktopfs"]
    rootfs, desktopfs = plan.layers
    assert rootfs.source == Path("/")
    assert desktopfs.source == workdir / "overlay"
    assert plan.overlay_dir == workdir / "overlay"


def test_resolve_plan_reset_rootfs_layer_excludes_home_and_account_files(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")

    plan = overlay.resolve_plan("reset", tmp_path / "work", exclude_list)
    rootfs = plan.layers[0]

    for pattern in ["home/*", "etc/passwd", "etc/shadow", "etc/gshadow", "etc/group", "etc/machine-id"]:
        assert pattern in rootfs.exclude_patterns


def test_resolve_plan_reset_desktopfs_layer_has_no_excludes(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("var/log/*\n")

    plan = overlay.resolve_plan("reset", tmp_path / "work", exclude_list)
    desktopfs = plan.layers[1]

    assert desktopfs.exclude_patterns == []


def test_resolve_plan_rootfs_layer_excludes_its_own_workdir(tmp_path):
    """Regression guard: the rootfs layer's source is '/' itself, so
    without this, mksquashfs recurses into its own workdir -- including
    the .sfs file it's writing, mid-write, growing every time it's
    re-read. Drove a real multi-hundred-GB runaway build."""
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")
    workdir = tmp_path / "var" / "lib" / "mabox-snapshot" / "work"

    plan = overlay.resolve_plan("preserving", workdir, exclude_list)

    expected = f"{workdir.relative_to('/')}/*"
    assert expected in plan.layers[0].exclude_patterns


def test_resolve_plan_rootfs_layer_excludes_separate_output_dir(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")
    workdir = tmp_path / "work"
    output_dir = tmp_path / "external" / "Mabox-Snapshots"

    plan = overlay.resolve_plan("preserving", workdir, exclude_list, output_dir=output_dir)

    assert f"{workdir.relative_to('/')}/*" in plan.layers[0].exclude_patterns
    assert f"{output_dir.relative_to('/')}/*" in plan.layers[0].exclude_patterns


def test_resolve_plan_threads_override_rules_into_rootfs_layer(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")
    override_rules = tmp_path / "overrides.list"
    override_rules.write_text("exclude home/*/Documents\ninclude home/*/Documents/Custom_map\n")
    (tmp_path / "home" / "alice" / "Documents" / "Custom_map").mkdir(parents=True)
    (tmp_path / "home" / "alice" / "Documents" / "Other").mkdir(parents=True)

    plan = overlay.resolve_plan(
        "preserving", tmp_path / "work", exclude_list,
        override_rules_path=override_rules, override_root=tmp_path,
    )

    assert "home/alice/Documents/Other" in plan.layers[0].exclude_patterns
    assert "home/alice/Documents/Custom_map" not in plan.layers[0].exclude_patterns


def test_resolve_plan_rejects_unknown_mode(tmp_path):
    with pytest.raises(ValueError):
        overlay.resolve_plan("bogus", tmp_path / "work", tmp_path / "excludes.list")


def test_each_layer_builds_as_a_single_source_squashfs_command(tmp_path):
    """Regression guard for the real bug this fixes: mksquashfs's -ef
    exclude patterns silently stop matching anything once given more than
    one source directory (verified empirically against a real mksquashfs
    build -- reset mode was shipping the full, unsanitized live system).
    Every layer must always be built as its own single-source invocation."""
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("")

    plan = overlay.resolve_plan("reset", tmp_path / "work", exclude_list)

    for layer in plan.layers:
        cmd = squashfs.build_command([layer.source], tmp_path / f"{layer.name}.sfs", None, "zstd", None)
        sources_in_cmd = cmd[1:-4]  # mksquashfs <sources...> <dest> -noappend -comp zstd
        assert sources_in_cmd == [str(layer.source)]


def test_build_overlay_noop_for_preserving_mode(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(overlay.seed, "seed_demo_home", lambda *a, **kw: called.append("seed"))
    monkeypatch.setattr(overlay.calamares, "build_calamares_branding", lambda *a, **kw: called.append("calamares"))
    monkeypatch.setattr(overlay.permissions, "normalize", lambda *a, **kw: called.append("normalize"))
    monkeypatch.setattr(overlay.sanitize, "write_sanitized_files", lambda *a, **kw: called.append("sanitize"))

    plan = overlay.BuildPlan(mode="preserving", layers=[], overlay_dir=None)
    overlay.build_overlay(plan)

    assert called == []


def test_build_overlay_reset_mode_populates_overlay_dir_in_order(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(overlay.seed, "seed_demo_home", lambda *a, **kw: called.append("seed"))
    monkeypatch.setattr(
        overlay.calamares, "build_calamares_branding", lambda *a, **kw: called.append("calamares") or True
    )
    monkeypatch.setattr(overlay.calamares, "write_removeuser_override", lambda *a, **kw: called.append("removeuser"))
    monkeypatch.setattr(overlay.permissions, "normalize", lambda *a, **kw: called.append("normalize"))
    monkeypatch.setattr(overlay.sanitize, "write_sanitized_files", lambda *a, **kw: called.append("sanitize"))

    plan = overlay.BuildPlan(mode="reset", layers=[], overlay_dir=tmp_path / "overlay")
    overlay.build_overlay(plan)

    assert called == ["seed", "calamares", "removeuser", "normalize", "sanitize"]


def test_build_overlay_reset_mode_writes_settings_override_when_branding_unconfigured(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(overlay.seed, "seed_demo_home", lambda *a, **kw: None)
    monkeypatch.setattr(overlay.calamares, "build_calamares_branding", lambda *a, **kw: False)
    monkeypatch.setattr(overlay.calamares, "write_settings_override", lambda *a, **kw: called.append("settings"))
    monkeypatch.setattr(overlay.calamares, "write_removeuser_override", lambda *a, **kw: called.append("removeuser"))
    monkeypatch.setattr(overlay.permissions, "normalize", lambda *a, **kw: None)
    monkeypatch.setattr(overlay.sanitize, "write_sanitized_files", lambda *a, **kw: None)

    plan = overlay.BuildPlan(mode="reset", layers=[], overlay_dir=tmp_path / "overlay")
    overlay.build_overlay(plan)

    assert called == ["settings", "removeuser"]
