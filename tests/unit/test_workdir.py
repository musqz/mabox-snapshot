import shutil

import pytest

from mabox_snapshot import workdir


def test_ensure_workdir_creates_nested_path(tmp_path):
    path = tmp_path / "a" / "b" / "c"
    result = workdir.ensure_workdir(path)

    assert result == path
    assert path.is_dir()


def test_check_free_space_skip_bypasses_check(tmp_path):
    workdir.check_free_space(tmp_path, required_bytes=10**18, skip=True)  # must not raise


def test_check_free_space_raises_when_insufficient(tmp_path):
    free = shutil.disk_usage(tmp_path).free
    with pytest.raises(workdir.InsufficientSpaceError):
        workdir.check_free_space(tmp_path, required_bytes=free + 10**12)


def test_check_free_space_passes_when_sufficient(tmp_path):
    workdir.check_free_space(tmp_path, required_bytes=1)  # must not raise


def test_cleanup_removes_workdir_unless_keep(tmp_path):
    path = tmp_path / "work"
    path.mkdir()
    (path / "file").write_text("x")

    workdir.cleanup(path, keep=True)
    assert path.exists()

    workdir.cleanup(path, keep=False)
    assert not path.exists()
