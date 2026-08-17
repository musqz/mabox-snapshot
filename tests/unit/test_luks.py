from pathlib import Path

import pytest

from mabox_snapshot import luks


def test_build_luks_format_command_uses_luks2_and_stdin_keyfile():
    cmd = luks.build_luks_format_command(Path("/tmp/container.luks"))
    assert "--type" in cmd and "luks2" in cmd
    assert "--key-file=-" in cmd
    assert cmd[-1] == "/tmp/container.luks"


def test_build_luks_format_command_is_batch_mode():
    cmd = luks.build_luks_format_command(Path("/tmp/container.luks"))
    assert "-q" in cmd


def test_build_losetup_attach_command_omits_read_only():
    cmd = luks.build_losetup_attach_command(Path("/tmp/container.luks"))
    assert "--read-only" not in cmd
    assert cmd == ["losetup", "--find", "--show", "/tmp/container.luks"]


def test_build_losetup_detach_command():
    assert luks.build_losetup_detach_command("/dev/loop7") == ["losetup", "-d", "/dev/loop7"]


def test_build_luks_open_command_uses_stdin_keyfile():
    cmd = luks.build_luks_open_command("/dev/loop7", "mabox_rootfs")
    assert "--key-file=-" in cmd
    assert cmd[-2:] == ["/dev/loop7", "mabox_rootfs"]


def test_build_luks_close_command():
    assert luks.build_luks_close_command("mabox_rootfs") == ["cryptsetup", "close", "mabox_rootfs"]


def test_build_dd_copy_command_uses_non_default_block_size():
    cmd = luks.build_dd_copy_command(Path("/tmp/rootfs.sfs"), "/dev/mapper/mabox_rootfs")
    assert "bs=4M" in cmd
    assert "conv=fsync" in cmd


def test_build_dd_copy_command_custom_block_size():
    cmd = luks.build_dd_copy_command(Path("/tmp/rootfs.sfs"), "/dev/mapper/mabox_rootfs", block_size="1M")
    assert "bs=1M" in cmd
    assert "bs=4M" not in cmd


def test_container_size_bytes_adds_margin():
    assert luks.container_size_bytes(1000) == 1000 + luks.LUKS_HEADER_MARGIN_BYTES


def test_create_container_file_creates_sparse_file_of_exact_size(tmp_path):
    path = tmp_path / "container.luks"
    size = 64 * 1024 * 1024

    luks.create_container_file(path, size)

    assert path.stat().st_size == size
    assert path.stat().st_blocks * 512 < size  # sparse, not really written


def test_check_hook_installed_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="package"):
        luks.check_hook_installed(tmp_path / "does-not-exist")


def test_check_hook_installed_passes_when_present(tmp_path):
    hook = tmp_path / "miso_luks"
    hook.write_text("# hook")
    luks.check_hook_installed(hook)  # must not raise


def test_prompt_for_passphrase_returns_when_entries_match(monkeypatch):
    monkeypatch.setattr(luks.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(luks.getpass, "getpass", lambda _: "correct horse")
    assert luks.prompt_for_passphrase() == "correct horse"


def test_prompt_for_passphrase_retries_on_mismatch_then_succeeds(monkeypatch):
    monkeypatch.setattr(luks.sys.stdin, "isatty", lambda: True)
    answers = iter(["first", "second", "match", "match"])
    monkeypatch.setattr(luks.getpass, "getpass", lambda _: next(answers))
    assert luks.prompt_for_passphrase() == "match"


def test_prompt_for_passphrase_rejects_empty_then_succeeds(monkeypatch):
    monkeypatch.setattr(luks.sys.stdin, "isatty", lambda: True)
    answers = iter(["", "ok", "ok"])
    monkeypatch.setattr(luks.getpass, "getpass", lambda _: next(answers))
    assert luks.prompt_for_passphrase() == "ok"


def test_prompt_for_passphrase_raises_when_not_interactive(monkeypatch):
    monkeypatch.setattr(luks.sys.stdin, "isatty", lambda: False)
    with pytest.raises(RuntimeError):
        luks.prompt_for_passphrase()
