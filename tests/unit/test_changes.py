import shutil
import subprocess
from pathlib import Path

import pytest

from mabox_snapshot import changes
from mabox_snapshot.history import HistoryEntry


def test_diff_entries_flags_new_entry_above_threshold():
    current = [HistoryEntry(name="Videos", type="dir", size_bytes=300 * 1024**2)]
    changed = changes.diff_entries([], current, threshold_bytes=200 * 1024**2)

    assert len(changed) == 1
    assert changed[0].name == "Videos"
    assert changed[0].is_new is True
    assert changed[0].delta_bytes == 300 * 1024**2


def test_diff_entries_ignores_new_entry_below_threshold():
    current = [HistoryEntry(name="notes.txt", type="file", size_bytes=10 * 1024**2)]
    assert changes.diff_entries([], current, threshold_bytes=200 * 1024**2) == []


def test_diff_entries_flags_grown_entry_above_threshold():
    previous = [HistoryEntry(name="Videos", type="dir", size_bytes=100 * 1024**2)]
    current = [HistoryEntry(name="Videos", type="dir", size_bytes=400 * 1024**2)]

    changed = changes.diff_entries(previous, current, threshold_bytes=200 * 1024**2)

    assert len(changed) == 1
    assert changed[0].is_new is False
    assert changed[0].delta_bytes == 300 * 1024**2


def test_diff_entries_ignores_shrunk_entry():
    previous = [HistoryEntry(name="Videos", type="dir", size_bytes=400 * 1024**2)]
    current = [HistoryEntry(name="Videos", type="dir", size_bytes=100 * 1024**2)]
    assert changes.diff_entries(previous, current, threshold_bytes=1) == []


def test_diff_entries_ignores_unchanged_entry():
    previous = [HistoryEntry(name="Videos", type="dir", size_bytes=100 * 1024**2)]
    current = [HistoryEntry(name="Videos", type="dir", size_bytes=100 * 1024**2)]
    assert changes.diff_entries(previous, current, threshold_bytes=1) == []


def test_diff_entries_boundary_growth_is_flagged():
    previous = [HistoryEntry(name="Videos", type="dir", size_bytes=100)]
    current = [HistoryEntry(name="Videos", type="dir", size_bytes=300)]
    changed = changes.diff_entries(previous, current, threshold_bytes=200)
    assert len(changed) == 1


def _entry(name, type="dir"):
    return changes.ChangedEntry(name=name, type=type, size_bytes=1, delta_bytes=1, is_new=True)


def test_exclude_patterns_dir_covers_visible_and_hidden_children():
    assert changes._exclude_patterns(Path("/home/alice"), _entry("Videos")) == [
        "home/alice/Videos/*",
        "home/alice/Videos/.*",
    ]


@pytest.mark.parametrize("name,escaped", [
    (".config/Foo [beta]", ".config/Foo \\[beta\\]"),
    ("a+(b)", "a\\+\\(b\\)"),
    ("x!(y)", "x\\!\\(y\\)"),
    ("star*?", "star\\*\\?"),
])
def test_exclude_patterns_escape_glob_characters(name, escaped):
    assert changes._exclude_patterns(Path("/home/alice"), _entry(name))[0] == f"home/alice/{escaped}/*"


def test_exclude_patterns_skip_newline_names():
    assert changes._exclude_patterns(Path("/home/alice"), _entry("a\nusr")) == []


@pytest.mark.skipif(not (shutil.which("mksquashfs") and shutil.which("unsquashfs")), reason="squashfs-tools not installed")
def test_exclude_patterns_match_in_mksquashfs(tmp_path):
    src = tmp_path / "src"
    home = src / "home"
    for d in ("a+(b)", "ab", ".config/Foo [beta]"):
        (home / d).mkdir(parents=True)
    (home / "a+(b)" / "f").write_text("x")
    (home / "a+(b)" / ".hidden").write_text("x")
    (home / "ab" / "f").write_text("x")
    (home / ".config/Foo [beta]" / "f").write_text("x")
    patterns = []
    for name in ("a+(b)", ".config/Foo [beta]"):
        patterns += changes._exclude_patterns(Path("/home"), _entry(name))
    ef = tmp_path / "ef"
    ef.write_text("\n".join(patterns) + "\n")
    img = tmp_path / "out.sqsh"
    subprocess.run(["mksquashfs", str(src), str(img), "-quiet", "-no-progress",
                    "-wildcards", "-ef", str(ef)], check=True, capture_output=True)
    listing = subprocess.run(["unsquashfs", "-l", str(img)], check=True,
                             capture_output=True, text=True).stdout
    assert "ab/f" in listing
    assert "a+(b)/f" not in listing and "a+(b)/.hidden" not in listing
    assert "Foo [beta]/f" not in listing


def test_exclude_pattern_file_has_no_trailing_glob():
    entry = changes.ChangedEntry(name="big.iso", type="file", size_bytes=1, delta_bytes=1, is_new=True)
    assert changes._exclude_patterns(Path("/home/alice"), entry) == ["home/alice/big.iso"]


def test_prompt_for_exclusions_no_changes_returns_empty():
    assert changes.prompt_for_exclusions([], Path("/home/alice")) == []


def test_prompt_for_exclusions_non_interactive_keeps_everything(monkeypatch, capsys):
    monkeypatch.setattr(changes.sys.stdin, "isatty", lambda: False)
    changed = [changes.ChangedEntry(name="Videos", type="dir", size_bytes=1, delta_bytes=1, is_new=True)]

    result = changes.prompt_for_exclusions(changed, Path("/home/alice"))

    assert result == []
    assert "non-interactive" in capsys.readouterr().out


def test_prompt_for_exclusions_default_keeps(monkeypatch):
    monkeypatch.setattr(changes.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "")
    changed = [changes.ChangedEntry(name="Videos", type="dir", size_bytes=1, delta_bytes=1, is_new=True)]

    assert changes.prompt_for_exclusions(changed, Path("/home/alice")) == []


def test_prompt_for_exclusions_e_excludes(monkeypatch):
    monkeypatch.setattr(changes.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "e")
    changed = [changes.ChangedEntry(name="Videos", type="dir", size_bytes=1, delta_bytes=1, is_new=True)]

    assert changes.prompt_for_exclusions(changed, Path("/home/alice")) == ["home/alice/Videos/*", "home/alice/Videos/.*"]


def test_prompt_for_exclusions_mixed_answers(monkeypatch):
    monkeypatch.setattr(changes.sys.stdin, "isatty", lambda: True)
    answers = iter(["e", "k"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    changed = [
        changes.ChangedEntry(name="Videos", type="dir", size_bytes=1, delta_bytes=1, is_new=True),
        changes.ChangedEntry(name="notes.txt", type="file", size_bytes=1, delta_bytes=1, is_new=True),
    ]

    assert changes.prompt_for_exclusions(changed, Path("/home/alice")) == ["home/alice/Videos/*", "home/alice/Videos/.*"]


def test_prompt_for_exclusions_eof_keeps_earlier_answers(monkeypatch):
    monkeypatch.setattr(changes.sys.stdin, "isatty", lambda: True)
    answers = iter(["e"])

    def fake_input(_):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    changed = [_entry("Videos"), _entry("Music")]

    assert changes.prompt_for_exclusions(changed, Path("/home/alice")) == [
        "home/alice/Videos/*",
        "home/alice/Videos/.*",
    ]
