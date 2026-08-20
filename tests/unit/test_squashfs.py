from mabox_snapshot import squashfs

FIXTURE_HELP_OUTPUT = """Filesystem compression options:
-b <block-size>\t\tset data block to <block-size>.
-comp <comp>\t\tselect <comp> compression.
\t\t\tCompressors available:
\t\t\t\tgzip (default)
\t\t\t\tlzo
\t\t\t\txz
-noI\t\t\tdo not compress inode table
"""


def test_parse_compressors_extracts_listed_and_preserves_our_order():
    result = squashfs._parse_compressors(FIXTURE_HELP_OUTPUT)
    assert result == ["xz", "lzo", "gzip"]


def test_parse_compressors_empty_when_section_missing():
    assert squashfs._parse_compressors("no compression info here") == []


def test_build_command_orders_sources_before_options():
    cmd = squashfs.build_command(
        sources=["/a", "/b"],
        dest="/out.sfs",
        exclude_file=None,
        compression="zstd",
        compression_level=None,
    )
    assert cmd[:4] == ["mksquashfs", "/a", "/b", "/out.sfs"]
    assert "-noappend" in cmd
    assert "-comp" in cmd and "zstd" in cmd


def test_build_command_includes_exclude_file_when_given():
    cmd = squashfs.build_command(["/a"], "/out.sfs", "/tmp/ex.list", "zstd", None)
    assert "-wildcards" in cmd
    assert "-ef" in cmd
    assert "/tmp/ex.list" in cmd


def test_build_command_omits_exclude_flags_when_none():
    cmd = squashfs.build_command(["/a"], "/out.sfs", None, "zstd", None)
    assert "-ef" not in cmd


def test_build_command_includes_compression_level_when_given():
    cmd = squashfs.build_command(["/a"], "/out.sfs", None, "zstd", 5)
    assert "-Xcompression-level" in cmd
    assert "5" in cmd


def test_build_command_includes_pseudo_file_specs_when_given():
    cmd = squashfs.build_command(["/a"], "/out.sfs", None, "zstd", None, pseudo_files=["etc/foo f 644 0 0 cat /bar"])
    assert cmd[-2:] == ["-p", "etc/foo f 644 0 0 cat /bar"]


def test_build_command_omits_pseudo_flags_when_none():
    cmd = squashfs.build_command(["/a"], "/out.sfs", None, "zstd", None)
    assert "-p" not in cmd


def test_build_command_includes_pseudo_file_list_when_given():
    cmd = squashfs.build_command(["/a"], "/out.sfs", None, "zstd", None, pseudo_file_list="/work/skel-pseudo.list")
    assert cmd[-2:] == ["-pf", "/work/skel-pseudo.list"]


def test_build_command_omits_pseudo_file_list_flag_when_none():
    cmd = squashfs.build_command(["/a"], "/out.sfs", None, "zstd", None)
    assert "-pf" not in cmd


def test_build_command_combines_p_specs_and_pf_list():
    cmd = squashfs.build_command(
        ["/a"], "/out.sfs", None, "zstd", None,
        pseudo_files=["etc/foo f 644 0 0 cat /bar"],
        pseudo_file_list="/work/skel-pseudo.list",
    )
    assert "-p" in cmd and "etc/foo f 644 0 0 cat /bar" in cmd
    assert cmd[-2:] == ["-pf", "/work/skel-pseudo.list"]
