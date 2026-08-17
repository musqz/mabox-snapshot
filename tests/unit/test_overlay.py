from pathlib import Path

import pytest

from mabox_snapshot import overlay, squashfs


def test_resolve_plan_preserving_has_single_rootfs_layer(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("var/log/*\n")

    plan = overlay.resolve_plan("preserving", tmp_path / "work", exclude_list)

    assert plan.overlay_dir is None
    assert [layer.name for layer in plan.layers] == ["rootfs"]
    assert plan.layers[0].source == Path("/")
    assert "var/log/*" in plan.layers[0].exclude_patterns


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
    monkeypatch.setattr(overlay.calamares, "build_calamares_branding", lambda *a, **kw: called.append("calamares"))
    monkeypatch.setattr(overlay.permissions, "normalize", lambda *a, **kw: called.append("normalize"))
    monkeypatch.setattr(overlay.sanitize, "write_sanitized_files", lambda *a, **kw: called.append("sanitize"))

    plan = overlay.BuildPlan(mode="reset", layers=[], overlay_dir=tmp_path / "overlay")
    overlay.build_overlay(plan)

    assert called == ["seed", "calamares", "normalize", "sanitize"]
