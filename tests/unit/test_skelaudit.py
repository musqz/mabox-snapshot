import pytest

from mabox_snapshot import skelaudit


def _write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_audit_home_against_skel_requires_skel_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        skelaudit.audit_home_against_skel(tmp_path / "home", skel_source=tmp_path / "no-skel")


def test_identical_file(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / ".config" / "openbox" / "rc.xml", "same content")
    _write(home / ".config" / "openbox" / "rc.xml", "same content")

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)

    entry = next(e for e in report.entries if e.rel_path == ".config/openbox/rc.xml")
    assert entry.status == "identical"


def test_differing_content(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / ".config" / "openbox" / "rc.xml", "default content")
    _write(home / ".config" / "openbox" / "rc.xml", "my hand-edited content")

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)

    entry = next(e for e in report.entries if e.rel_path == ".config/openbox/rc.xml")
    assert entry.status == "differs"


def test_missing_file(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / ".config" / "openbox" / "rc.xml", "default content")
    home.mkdir()

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)

    entry = next(e for e in report.entries if e.rel_path == ".config/openbox/rc.xml")
    assert entry.status == "missing"


def test_symlink_identical_and_differs_by_target(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    skel.mkdir()
    home.mkdir()
    (skel / "target-a").write_text("a")
    (skel / "target-b").write_text("b")
    (skel / "link.conf").symlink_to("target-a")
    (home / "link.conf").symlink_to("target-a")

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)
    entry = next(e for e in report.entries if e.rel_path == "link.conf")
    assert entry.status == "identical"

    (home / "link.conf").unlink()
    (home / "link.conf").symlink_to("target-b")
    report = skelaudit.audit_home_against_skel(home, skel_source=skel)
    entry = next(e for e in report.entries if e.rel_path == "link.conf")
    assert entry.status == "differs"


def test_type_mismatch_is_differs(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / "thing", "file content")
    (home / "thing").mkdir(parents=True)

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)
    entry = next(e for e in report.entries if e.rel_path == "thing")
    assert entry.status == "differs"


def test_fully_custom_app_dir_reported_once_in_bulk(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / ".config" / "openbox" / "rc.xml", "default")
    _write(home / ".config" / "openbox" / "rc.xml", "default")
    _write(home / ".config" / "discord" / "settings.json", "{}")
    _write(home / ".config" / "discord" / "cache" / "blob", "x")

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)

    custom = report.by_status("custom")
    assert [e.rel_path for e in custom] == [".config/discord/"]


def test_top_level_unrelated_home_content_never_visited(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / ".config" / "openbox" / "rc.xml", "default")
    _write(home / ".config" / "openbox" / "rc.xml", "default")
    _write(home / "Documents" / "notes.txt", "private notes")
    _write(home / ".ssh" / "id_ed25519", "private key")

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)

    assert not any(e.rel_path.startswith("Documents") for e in report.entries)
    assert not any(e.rel_path.startswith(".ssh") for e in report.entries)


def test_skel_covered_dir_with_extra_local_files_keeps_file_level_granularity(tmp_path):
    skel = tmp_path / "skel"
    home = tmp_path / "home"
    _write(skel / ".config" / "openbox" / "rc.xml", "default")
    _write(skel / ".config" / "openbox" / "menu.xml", "default menu")
    _write(home / ".config" / "openbox" / "rc.xml", "default")
    _write(home / ".config" / "openbox" / "menu.xml", "my custom menu")
    _write(home / ".config" / "openbox" / "my-extra-script.sh", "#!/bin/sh")

    report = skelaudit.audit_home_against_skel(home, skel_source=skel)

    by_path = {e.rel_path: e.status for e in report.entries}
    assert by_path[".config/openbox/rc.xml"] == "identical"
    assert by_path[".config/openbox/menu.xml"] == "differs"
    assert by_path[".config/openbox/my-extra-script.sh"] == "custom"


def test_format_report_groups_and_gates_identical():
    report = skelaudit.AuditReport(
        entries=[
            skelaudit.AuditEntry("a", "identical"),
            skelaudit.AuditEntry("b", "differs"),
            skelaudit.AuditEntry("c", "missing"),
            skelaudit.AuditEntry("d/", "custom"),
        ]
    )

    hidden = skelaudit.format_report(report, show_identical=False)
    assert "identical: 1 (use --show-identical to list)" in hidden
    assert "  a" not in hidden
    assert "  b" in hidden
    assert "  c" in hidden
    assert "  d/" in hidden

    shown = skelaudit.format_report(report, show_identical=True)
    assert "identical (1):" in shown
    assert "  a" in shown
