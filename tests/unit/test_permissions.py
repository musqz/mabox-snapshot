import os
import stat

from mabox_snapshot import permissions


def _mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def test_normalize_fixes_umask_shrunk_dirs_and_files(tmp_path):
    old_umask = os.umask(0o077)  # deliberately restrictive, mimics the real bug
    try:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "file.txt").write_text("hi")
    finally:
        os.umask(old_umask)

    assert _mode(tmp_path / "sub") != permissions.DIR_MODE  # sanity: umask actually shrunk it

    permissions.normalize(tmp_path)

    assert _mode(tmp_path) == permissions.DIR_MODE
    assert _mode(tmp_path / "sub") == permissions.DIR_MODE
    assert _mode(tmp_path / "sub" / "file.txt") == permissions.FILE_MODE


def test_normalize_preserves_executable_bit(tmp_path):
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o700)

    permissions.normalize(tmp_path)

    assert _mode(script) == permissions.EXEC_FILE_MODE


def test_normalize_never_follows_symlinks(tmp_path):
    outside = tmp_path.parent / "outside-target"
    outside.mkdir(exist_ok=True)
    outside.chmod(0o700)
    (tmp_path / "link-to-outside").symlink_to(outside)

    permissions.normalize(tmp_path)

    assert _mode(outside) == 0o700  # untouched


def test_normalize_continues_after_one_chmod_failure(tmp_path, monkeypatch, caplog):
    (tmp_path / "a").write_text("a")
    (tmp_path / "b").write_text("b")

    real_chmod = os.chmod

    def flaky_chmod(path, mode):
        if str(path).endswith("/a"):
            raise OSError("simulated failure")
        real_chmod(path, mode)

    monkeypatch.setattr(os, "chmod", flaky_chmod)

    permissions.normalize(tmp_path)  # must not raise

    assert _mode(tmp_path / "b") == permissions.FILE_MODE
