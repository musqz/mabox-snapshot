from pathlib import Path

import pytest

from mabox_snapshot import privilege


def test_resolve_home_dir_uses_sudo_user_env(monkeypatch):
    monkeypatch.setenv("SUDO_USER", "alice")
    assert privilege.resolve_home_dir() == Path("/home/alice")


def test_resolve_home_dir_raises_when_sudo_user_unset(monkeypatch):
    monkeypatch.delenv("SUDO_USER", raising=False)
    with pytest.raises(privilege.NoSudoUserError):
        privilege.resolve_home_dir()
