import os
from datetime import datetime, timedelta

from mabox_snapshot import retention


def _make_iso(path, age_days, now):
    path.write_bytes(b"x")
    mtime = (now - timedelta(days=age_days)).timestamp()
    os.utime(path, (mtime, mtime))


def test_prune_old_isos_removes_only_files_older_than_max_age(tmp_path):
    now = datetime(2026, 8, 17, 12, 0, 0)
    old = tmp_path / "mabox-preserving-old.iso"
    recent = tmp_path / "mabox-preserving-recent.iso"
    _make_iso(old, age_days=100, now=now)
    _make_iso(recent, age_days=1, now=now)

    deleted = retention.prune_old_isos(tmp_path, max_age_days=45, now=now)

    assert deleted == [old]
    assert not old.exists()
    assert recent.exists()


def test_prune_old_isos_ignores_non_mabox_isos(tmp_path):
    now = datetime(2026, 8, 17, 12, 0, 0)
    foreign = tmp_path / "ubuntu.iso"
    _make_iso(foreign, age_days=1000, now=now)

    deleted = retention.prune_old_isos(tmp_path, max_age_days=1, now=now)

    assert deleted == []
    assert foreign.exists()


def test_prune_old_isos_ignores_non_iso_files(tmp_path):
    now = datetime(2026, 8, 17, 12, 0, 0)
    other = tmp_path / "mabox-preserving-old.toml"
    _make_iso(other, age_days=1000, now=now)

    deleted = retention.prune_old_isos(tmp_path, max_age_days=1, now=now)

    assert deleted == []
    assert other.exists()


def test_prune_old_isos_missing_output_dir_returns_empty(tmp_path):
    assert retention.prune_old_isos(tmp_path / "does-not-exist", max_age_days=1) == []


def test_prune_old_isos_boundary_age_is_kept(tmp_path):
    now = datetime(2026, 8, 17, 12, 0, 0)
    boundary = tmp_path / "mabox-preserving-boundary.iso"
    _make_iso(boundary, age_days=45, now=now)

    deleted = retention.prune_old_isos(tmp_path, max_age_days=45, now=now)

    assert deleted == []
    assert boundary.exists()
