from pathlib import Path

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


def test_exclude_pattern_dir_gets_trailing_glob():
    entry = changes.ChangedEntry(name="Videos", type="dir", size_bytes=1, delta_bytes=1, is_new=True)
    assert changes._exclude_pattern(Path("/home/alice"), entry) == "home/alice/Videos/*"


def test_exclude_pattern_file_has_no_trailing_glob():
    entry = changes.ChangedEntry(name="big.iso", type="file", size_bytes=1, delta_bytes=1, is_new=True)
    assert changes._exclude_pattern(Path("/home/alice"), entry) == "home/alice/big.iso"


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

    assert changes.prompt_for_exclusions(changed, Path("/home/alice")) == ["home/alice/Videos/*"]


def test_prompt_for_exclusions_mixed_answers(monkeypatch):
    monkeypatch.setattr(changes.sys.stdin, "isatty", lambda: True)
    answers = iter(["e", "k"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    changed = [
        changes.ChangedEntry(name="Videos", type="dir", size_bytes=1, delta_bytes=1, is_new=True),
        changes.ChangedEntry(name="notes.txt", type="file", size_bytes=1, delta_bytes=1, is_new=True),
    ]

    assert changes.prompt_for_exclusions(changed, Path("/home/alice")) == ["home/alice/Videos/*"]
