from mabox_snapshot import excludes


def test_parse_lines_skips_comments_and_blanks():
    text = "\n# comment\ndev/*\n\nproc/*\n  # indented comment\n"
    assert excludes._parse_lines(text) == ["dev/*", "proc/*"]


def test_exclude_list_add_dedupes_and_persists(tmp_path):
    path = tmp_path / "excludes.list"
    el = excludes.ExcludeList(path)
    el.add("dev/*")
    el.add("dev/*")
    el.add("proc/*")

    assert el.load() == ["dev/*", "proc/*"]


def test_exclude_list_remove(tmp_path):
    path = tmp_path / "excludes.list"
    el = excludes.ExcludeList(path)
    el.add("dev/*")
    el.add("proc/*")
    el.remove("dev/*")

    assert el.load() == ["proc/*"]


def test_exclude_list_reset_requires_shipped_default(tmp_path):
    path = tmp_path / "excludes.list"
    missing_default = tmp_path / "nope.default"
    try:
        excludes.ExcludeList(path).reset(default_source=missing_default)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_resolve_user_dirs_parses_shell_style_file(tmp_path):
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    (home / ".config" / "user-dirs.dirs").write_text(
        'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
        'XDG_DOWNLOAD_DIR="$HOME/Descargas"\n'  # localized name, path key stays XDG_DOWNLOAD_DIR
        "# a comment\n"
    )

    result = excludes.resolve_user_dirs(home)
    assert result["Desktop"] == home / "Desktop"
    assert result["Download"] == home / "Descargas"


def test_resolve_folder_excludes_relative_path(tmp_path):
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    (home / ".config" / "user-dirs.dirs").write_text('XDG_DOWNLOAD_DIR="$HOME/Downloads"\n')

    result = excludes.resolve_folder_excludes(("Download", "Videos"), home=home)
    expected_rel = str((home / "Downloads").relative_to("/"))
    assert result == [f"{expected_rel}/*"]


def test_detect_swap_paths_skips_uuid_entries(tmp_path):
    fstab = tmp_path / "fstab"
    fstab.write_text(
        "UUID=abc-123 none swap defaults 0 0\n"
        "/swapfile none swap defaults 0 0\n"
        "/dev/sda1 / ext4 defaults 0 1\n"
    )

    assert excludes.detect_swap_paths(fstab) == ["swapfile"]


def test_resolve_excludes_adds_reset_mode_only_patterns(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("dev/*\n")
    fstab = tmp_path / "fstab"
    fstab.write_text("")

    preserving = excludes.resolve_excludes("preserving", exclude_list, fstab=fstab)
    reset = excludes.resolve_excludes("reset", exclude_list, fstab=fstab)

    assert "home/*" not in preserving
    assert "home/*" in reset


def test_resolve_excludes_deduplicates(tmp_path):
    exclude_list = tmp_path / "excludes.list"
    exclude_list.write_text("dev/*\ndev/*\n")
    fstab = tmp_path / "fstab"
    fstab.write_text("")

    result = excludes.resolve_excludes("preserving", exclude_list, fstab=fstab)
    assert result.count("dev/*") == 1
