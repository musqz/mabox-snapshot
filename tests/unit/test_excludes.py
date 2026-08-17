import os
from pathlib import Path
from types import SimpleNamespace

from mabox_snapshot import excludes

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _fake_stat(devs):
    """os.stat() replacement for a specific set of test paths, real
    os.stat() for everything else -- os.stat is process-global, and
    Python's own internals (linecache, traceback formatting) call it on
    arbitrary paths while a test's monkeypatch is active, so a mock that
    only knows its own test's paths must fall through rather than raise."""
    real_stat = os.stat

    def fake(path, *args, **kwargs):
        key = str(path)
        if key in devs:
            return SimpleNamespace(st_dev=devs[key])
        return real_stat(path, *args, **kwargs)

    return fake


def test_shipped_default_parses_and_includes_curated_home_bloat_entries():
    default_path = REPO_ROOT / "configs" / "excludes.list.default"
    patterns = excludes._parse_lines(default_path.read_text())

    assert len(patterns) > 0
    assert "home/*/.cache/mozilla/firefox/*/cache2/*" in patterns
    assert "home/*/.var/app/*/cache/*" in patterns
    # Curated, not a blanket wipe -- .cache and .var themselves must never
    # appear bare, only specific known-large subpaths within them.
    assert "home/*/.cache/*" not in patterns
    assert "home/*/.var/*" not in patterns


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


def test_detect_foreign_mount_excludes_skips_root_and_allowed(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(
        f"/dev/sda1 {root} ext4 rw 0 1\n"
        f"/dev/sda2 {root / 'boot'} ext4 rw 0 2\n"
        f"/dev/sdb1 {root / 'mount' / 'data_opslag'} ext4 rw 0 0\n"
        f"/dev/sdc1 {tmp_path / 'outside'} ext4 rw 0 0\n"
    )

    result = excludes.detect_foreign_mount_excludes(
        root=root, allowed=(root / "boot",), mounts=mounts
    )

    assert result == ["mount/data_opslag/*"]


def test_detect_foreign_mount_excludes_allows_mounts_nested_under_allowed_root(tmp_path):
    """Regression guard: a separate EFI System Partition at /boot/efi is
    the default UEFI layout on Arch/Manjaro. It must not be treated as
    foreign just because it isn't an exact match for the allowed /boot
    entry -- it's mounted *under* /boot, which is fully allowed."""
    root = tmp_path / "root"
    root.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(
        f"/dev/sda1 {root} ext4 rw 0 1\n"
        f"/dev/sda2 {root / 'boot' / 'efi'} vfat rw 0 2\n"
    )

    result = excludes.detect_foreign_mount_excludes(
        root=root, allowed=(root / "boot",), mounts=mounts
    )

    assert result == []


def test_detect_foreign_mount_excludes_unescapes_spaces(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 {root / 'run' / 'media' / 'My\\040Passport'} ext4 rw 0 0\n")

    result = excludes.detect_foreign_mount_excludes(root=root, allowed=(), mounts=mounts)

    assert result == ["run/media/My Passport/*"]


def test_detect_foreign_mount_excludes_unescapes_tab_and_backslash(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 {root}/weird\\011\\134name ext4 rw 0 0\n")

    result = excludes.detect_foreign_mount_excludes(root=root, allowed=(), mounts=mounts)

    assert result == ["weird\t\\\\name/*"]


def test_detect_foreign_mount_excludes_skips_embedded_newline(tmp_path):
    """A literal newline in a mountpoint can't be represented as a single
    line in the newline-delimited -ef exclude file mksquashfs reads, so
    it's dropped rather than corrupting the file with a bogus extra line."""
    root = tmp_path / "root"
    root.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 {root}/weird\\012name ext4 rw 0 0\n")

    result = excludes.detect_foreign_mount_excludes(root=root, allowed=(), mounts=mounts)

    assert result == []


def test_detect_foreign_mount_excludes_escapes_glob_metacharacters(tmp_path):
    """A removable drive labeled e.g. 'Backup [2024]' must not have its
    exclude pattern misparsed as a glob character class by mksquashfs's
    -wildcards mode, or the exclude silently fails to match anything."""
    root = tmp_path / "root"
    root.mkdir()
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 {root / 'run' / 'media'}/Backup\\040[2024] ext4 rw 0 0\n")

    result = excludes.detect_foreign_mount_excludes(root=root, allowed=(), mounts=mounts)

    assert result == ["run/media/Backup \\[2024\\]/*"]


def test_detect_foreign_mount_excludes_allows_same_device_subvolume(tmp_path, monkeypatch):
    """Regression guard for Btrfs subvolume layouts (@, @home, @var, ...),
    a common Arch/Manjaro setup: each subvolume gets its own /proc/mounts
    entry with its own mountpoint but shares the parent filesystem's
    device id, so it must not be treated as foreign/removable storage."""
    root = tmp_path / "root"
    root.mkdir()
    var_mount = root / "var"
    mounts = tmp_path / "mounts"
    mounts.write_text(
        f"/dev/sda1 {root} btrfs rw,subvol=/@ 0 0\n"
        f"/dev/sda1 {var_mount} btrfs rw,subvol=/@var 0 0\n"
    )
    devs = {str(root): 1, str(var_mount): 1}  # same device -- a subvolume, not foreign
    monkeypatch.setattr(excludes.os, "stat", _fake_stat(devs))

    result = excludes.detect_foreign_mount_excludes(root=root, allowed=(), mounts=mounts)

    assert result == []


def test_detect_foreign_mount_excludes_excludes_different_device_mount(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    data = root / "mount" / "data"
    mounts = tmp_path / "mounts"
    mounts.write_text(f"/dev/sdb1 {data} ext4 rw 0 0\n")
    devs = {str(root): 1, str(data): 2}  # a genuinely separate volume
    monkeypatch.setattr(excludes.os, "stat", _fake_stat(devs))

    result = excludes.detect_foreign_mount_excludes(root=root, allowed=(), mounts=mounts)

    assert result == ["mount/data/*"]


def test_detect_foreign_mount_excludes_missing_mounts_file(tmp_path):
    assert excludes.detect_foreign_mount_excludes(mounts=tmp_path / "nope") == []


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
