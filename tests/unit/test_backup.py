from pathlib import Path

from mabox_snapshot import backup


def test_build_rsync_command_uses_archive_mode():
    cmd = backup.build_rsync_command(Path("/tmp/mabox-preserving-x.iso"), "/mnt/external/")
    assert cmd == ["rsync", "-a", "/tmp/mabox-preserving-x.iso", "/mnt/external/"]


def test_build_rsync_command_supports_ssh_target():
    cmd = backup.build_rsync_command(Path("/tmp/x.iso"), "alice@nas:/backups/mabox/")
    assert cmd[-1] == "alice@nas:/backups/mabox/"


def test_push_to_destinations_all_succeed(monkeypatch):
    calls = []
    monkeypatch.setattr(backup.subprocess, "run", lambda cmd, **kw: calls.append(cmd))

    failed = backup.push_to_destinations(Path("/tmp/x.iso"), ("/mnt/a/", "/mnt/b/"))

    assert failed == []
    assert len(calls) == 2


def test_push_to_destinations_returns_failed_ones(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kw):
        if "bad" in cmd[-1]:
            raise sp.CalledProcessError(1, cmd)

    monkeypatch.setattr(backup.subprocess, "run", fake_run)

    failed = backup.push_to_destinations(Path("/tmp/x.iso"), ("/mnt/good/", "/mnt/bad/"))

    assert failed == ["/mnt/bad/"]


def test_push_to_destinations_continues_after_failure(monkeypatch):
    import subprocess as sp

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if calls[0] is cmd:
            raise sp.CalledProcessError(1, cmd)

    monkeypatch.setattr(backup.subprocess, "run", fake_run)

    failed = backup.push_to_destinations(Path("/tmp/x.iso"), ("/mnt/fails/", "/mnt/succeeds/"))

    assert len(calls) == 2  # the second destination still ran
    assert failed == ["/mnt/fails/"]


def test_push_to_destinations_empty_returns_empty():
    assert backup.push_to_destinations(Path("/tmp/x.iso"), ()) == []
