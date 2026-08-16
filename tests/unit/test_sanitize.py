from mabox_snapshot import sanitize

PASSWD = """root:x:0:0::/root:/usr/bin/bash
bin:x:1:1::/:/usr/bin/nologin
dhcpcd:x:978:978:dhcpcd privilege separation:/:/usr/bin/nologin
vogel:x:1000:1001:vogel:/home/vogel:/bin/bash
leonie:x:1001:1001:leonie:/home/leonie:/bin/bash
"""

SHADOW = """root:!:19700:0:99999:7:::
bin:!:19700:0:99999:7:::
dhcpcd:!:19700:0:99999:7:::
vogel:$6$fakehash:19700:0:99999:7:::
leonie:$6$otherhash:19700:0:99999:7:::
"""

GROUP = """root:x:0:root
bin:x:1:daemon
wheel:x:998:vogel
video:x:983:vogel,dhcpcd
autologin:x:1000:vogel
vogel:x:1001:
leonie:x:1002:
"""

GSHADOW = """root:!::
wheel:!::vogel
video:!::vogel,dhcpcd
autologin:!::vogel
"""

SUBUID = """vogel:100000:65536
leonie:165536:65536
"""


def test_sanitize_passwd_drops_human_accounts_and_appends_demo():
    result = sanitize.sanitize_passwd(PASSWD.splitlines())

    names = [line.split(":")[0] for line in result]
    assert names == ["root", "bin", "dhcpcd", "demo"]
    assert result[-1] == "demo:x:1000:1000:demo:/home/demo:/bin/bash"


def test_system_account_names_excludes_human_accounts():
    names = sanitize.system_account_names(PASSWD.splitlines())
    assert names == {"root", "bin", "dhcpcd"}


def test_sanitize_shadow_keeps_only_system_rows_and_appends_demo_hash():
    system_names = sanitize.system_account_names(PASSWD.splitlines())
    result = sanitize.sanitize_shadow(SHADOW.splitlines(), system_names, "$6$demohash")

    names = [line.split(":")[0] for line in result]
    assert names == ["root", "bin", "dhcpcd", "demo"]
    assert result[-1].startswith("demo:$6$demohash:")


def test_sanitize_group_drops_dynamic_groups_and_scrubs_membership():
    system_names = sanitize.system_account_names(PASSWD.splitlines())
    result = sanitize.sanitize_group(GROUP.splitlines(), system_names)
    by_name = {line.split(":")[0]: line for line in result}

    assert "autologin" not in by_name  # gid 1000 -- dynamic, dropped entirely
    assert "vogel" not in by_name  # gid 1001 -- dynamic, dropped entirely
    assert "leonie" not in by_name
    assert by_name["wheel"] == "wheel:x:998:demo"  # baseline group: vogel scrubbed, demo added
    assert by_name["video"] == "video:x:983:dhcpcd,demo"  # dhcpcd retained -- it's a system account
    assert by_name["demo"] == "demo:x:1000:"


def test_sanitize_gshadow_matches_retained_groups_only():
    system_names = sanitize.system_account_names(PASSWD.splitlines())
    group_result = sanitize.sanitize_group(GROUP.splitlines(), system_names)
    retained_group_names = {line.split(":")[0] for line in group_result}

    result = sanitize.sanitize_gshadow(GSHADOW.splitlines(), system_names, retained_group_names)
    by_name = {line.split(":")[0]: line for line in result}

    assert "autologin" not in by_name
    assert by_name["wheel"] == "wheel:!::demo"
    assert by_name["demo"] == "demo:!::"


def test_sanitize_subid_drops_human_accounts_without_adding_demo():
    system_names = sanitize.system_account_names(PASSWD.splitlines())
    result = sanitize.sanitize_subid(SUBUID.splitlines(), system_names)
    assert result == []


def test_write_sanitized_files_chmods_shadow_files(tmp_path, monkeypatch):
    source_root = tmp_path / "root"
    (source_root / "etc").mkdir(parents=True)
    (source_root / "etc/passwd").write_text(PASSWD)
    (source_root / "etc/shadow").write_text(SHADOW)
    (source_root / "etc/group").write_text(GROUP)
    (source_root / "etc/gshadow").write_text(GSHADOW)

    monkeypatch.setattr(sanitize, "hash_demo_password", lambda password="demo": "$6$fixedhash")

    overlay_dir = tmp_path / "overlay"
    sanitize.write_sanitized_files(overlay_dir, source_root)

    assert (overlay_dir / "etc/passwd").stat().st_mode & 0o777 == 0o644
    assert (overlay_dir / "etc/shadow").stat().st_mode & 0o777 == 0o640
    assert (overlay_dir / "etc/gshadow").stat().st_mode & 0o777 == 0o640
    assert "demo:$6$fixedhash:" in (overlay_dir / "etc/shadow").read_text()
