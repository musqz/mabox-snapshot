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
