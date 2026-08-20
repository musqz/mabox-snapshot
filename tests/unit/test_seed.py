import pytest

from mabox_snapshot import seed


def test_seed_demo_home_copies_and_chowns(tmp_path, monkeypatch):
    skel_source = tmp_path / "skel"
    (skel_source / ".config" / "openbox").mkdir(parents=True)
    (skel_source / ".config" / "openbox" / "rc.xml").write_text("<config/>")

    chowned = []
    monkeypatch.setattr(
        seed.os,
        "chown",
        lambda path, uid, gid, follow_symlinks=True: chowned.append((str(path), uid, gid)),
    )

    overlay_dir = tmp_path / "overlay"
    dest = seed.seed_demo_home(overlay_dir, skel_source)

    assert dest == overlay_dir / "home" / "demo"
    assert (dest / ".config" / "openbox" / "rc.xml").read_text() == "<config/>"
    assert len(chowned) >= 3
    assert all(uid == 1000 and gid == 1000 for _, uid, gid in chowned)


def test_seed_demo_home_raises_when_skel_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        seed.seed_demo_home(tmp_path / "overlay", tmp_path / "does-not-exist")


def test_seed_etc_skel_copies_and_chowns_root(tmp_path, monkeypatch):
    skel_source = tmp_path / "skel"
    (skel_source / ".config" / "openbox").mkdir(parents=True)
    (skel_source / ".config" / "openbox" / "rc.xml").write_text("<config/>")

    chowned = []
    monkeypatch.setattr(
        seed.os,
        "chown",
        lambda path, uid, gid, follow_symlinks=True: chowned.append((str(path), uid, gid)),
    )

    overlay_dir = tmp_path / "overlay"
    dest = seed.seed_etc_skel(overlay_dir, skel_source)

    assert dest == overlay_dir / "etc" / "skel"
    assert (dest / ".config" / "openbox" / "rc.xml").read_text() == "<config/>"
    assert len(chowned) >= 3
    assert all(uid == 0 and gid == 0 for _, uid, gid in chowned)


def test_seed_etc_skel_raises_when_skel_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        seed.seed_etc_skel(tmp_path / "overlay", tmp_path / "does-not-exist")


def test_etc_skel_pseudo_specs_declares_dirs_before_their_contents(tmp_path):
    skel_source = tmp_path / "skel"
    (skel_source / ".config" / "openbox").mkdir(parents=True)
    (skel_source / ".config" / "openbox" / "rc.xml").write_text("<config/>")

    specs = seed.etc_skel_pseudo_specs(skel_source)

    assert specs[0] == "etc/skel d 755 0 0"
    config_idx = specs.index("etc/skel/.config d 755 0 0")
    openbox_idx = specs.index("etc/skel/.config/openbox d 755 0 0")
    file_spec = next(s for s in specs if s.startswith("etc/skel/.config/openbox/rc.xml"))
    file_idx = specs.index(file_spec)
    assert config_idx < openbox_idx < file_idx


def test_etc_skel_pseudo_specs_targets_and_quotes_correctly(tmp_path):
    skel_source = tmp_path / "skel"
    skel_source.mkdir()
    (skel_source / "rc.xml").write_text("<config/>")

    specs = seed.etc_skel_pseudo_specs(skel_source)

    file_spec = next(s for s in specs if s.startswith("etc/skel/rc.xml"))
    assert file_spec == f"etc/skel/rc.xml f 644 0 0 cat {skel_source / 'rc.xml'}"


def test_etc_skel_pseudo_specs_preserves_the_executable_bit(tmp_path):
    """Regression guard: tint2's Executor plugin runs some vendored skel
    scripts directly (e.g. .config/tint2/scripts/*) -- a flat 644 for
    every file would silently break them on preserving-mode installs,
    where seed_etc_skel()'s overlay-copytree path (reset mode) already
    preserves modes correctly and this pseudo-file path must match it."""
    skel_source = tmp_path / "skel"
    skel_source.mkdir()
    (skel_source / "plain.conf").write_text("x")
    script = skel_source / "script.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o755)

    specs = seed.etc_skel_pseudo_specs(skel_source)

    plain_spec = next(s for s in specs if s.startswith("etc/skel/plain.conf"))
    script_spec = next(s for s in specs if s.startswith("etc/skel/script.sh"))
    assert plain_spec.split()[2] == "644"
    assert script_spec.split()[2] == "755"


def test_etc_skel_pseudo_specs_quotes_a_path_with_spaces(tmp_path):
    skel_source = tmp_path / "skel"
    (skel_source / "sub dir").mkdir(parents=True)
    (skel_source / "sub dir" / "a file").write_text("x")

    specs = seed.etc_skel_pseudo_specs(skel_source)

    file_spec = next(s for s in specs if "a file" in s)
    assert "'" in file_spec  # shlex.quote wraps the space-containing source path


def test_etc_skel_pseudo_specs_raises_when_skel_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        seed.etc_skel_pseudo_specs(tmp_path / "does-not-exist")
