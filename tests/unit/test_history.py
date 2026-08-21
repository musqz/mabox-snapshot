import tomllib

import pytest

from mabox_snapshot import history


def test_scan_home_entries_top_level_only(tmp_path):
    home = tmp_path / "home"
    (home / "Videos" / "sub").mkdir(parents=True)
    (home / "Videos" / "movie.mp4").write_bytes(b"x" * 100)
    (home / "Videos" / "sub" / "clip.mp4").write_bytes(b"x" * 50)
    (home / "a.txt").write_bytes(b"x" * 10)

    entries = history.scan_home_entries(home)

    assert {(e.name, e.type) for e in entries} == {("Videos", "dir"), ("a.txt", "file")}


def test_scan_home_entries_dir_size_sums_nested_files(tmp_path):
    home = tmp_path / "home"
    (home / "Videos" / "nested").mkdir(parents=True)
    (home / "Videos" / "a").write_bytes(b"x" * 2000)
    (home / "Videos" / "nested" / "b").write_bytes(b"x" * 3000)

    entries = history.scan_home_entries(home)

    videos = next(e for e in entries if e.name == "Videos")
    assert videos.size_bytes == 5000


def test_scan_home_entries_file_size_is_own_size(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "a.txt").write_bytes(b"x" * 1234)

    entries = history.scan_home_entries(home)

    assert entries == [history.HistoryEntry(name="a.txt", type="file", size_bytes=1234)]


def test_scan_home_entries_empty_home_returns_empty_list(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert history.scan_home_entries(home) == []


def test_scan_home_entries_nonexistent_home_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        history.scan_home_entries(tmp_path / "does-not-exist")


def test_render_manifest_produces_expected_toml_shape():
    record = history.HistoryRecord(
        timestamp="2026-08-17T14:32:00",
        mode="preserving",
        iso="mabox-preserving-2026-08-17-1432.iso",
        entries=[
            history.HistoryEntry(name="Videos", type="dir", size_bytes=48318382080),
            history.HistoryEntry(name="a.txt", type="file", size_bytes=10),
        ],
    )

    rendered = history.render_manifest(record)

    assert 'mode = "preserving"' in rendered
    assert "[[entries]]" in rendered
    assert 'name = "Videos"' in rendered
    assert "size_bytes = 48318382080" in rendered

    parsed = tomllib.loads(rendered)
    assert parsed["mode"] == "preserving"
    assert parsed["iso"] == "mabox-preserving-2026-08-17-1432.iso"
    assert len(parsed["entries"]) == 2


def test_render_manifest_empty_entries_omits_entries_key():
    record = history.HistoryRecord(timestamp="2026-08-17T14:32:00", mode="reset", iso="x.iso", entries=[])
    parsed = tomllib.loads(history.render_manifest(record))
    assert not parsed.get("entries")


def test_render_manifest_escapes_quotes_and_backslashes():
    record = history.HistoryRecord(
        timestamp="2026-08-17T14:32:00",
        mode="preserving",
        iso="x.iso",
        entries=[history.HistoryEntry(name='weird"name\\here', type="file", size_bytes=1)],
    )

    parsed = tomllib.loads(history.render_manifest(record))
    assert parsed["entries"][0]["name"] == 'weird"name\\here'


def test_write_manifest_round_trip(tmp_path):
    home = tmp_path / "home"
    (home / "Videos").mkdir(parents=True)
    (home / "Videos" / "a").write_bytes(b"x" * 100)
    history_dir = tmp_path / "history"
    dest = tmp_path / "out" / "mabox-preserving-2026-08-17-1432.iso"

    written = history.write_manifest(dest, "preserving", history_dir=history_dir, home=home)

    assert written == history_dir / "mabox-preserving-2026-08-17-1432.toml"
    [record] = history.list_history(history_dir)
    assert record.mode == "preserving"
    assert record.iso == "mabox-preserving-2026-08-17-1432.iso"
    assert record.entries == history.scan_home_entries(home)


def test_write_manifest_uses_explicit_timestamp_when_given(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "history"

    history.write_manifest(
        tmp_path / "a.iso", "preserving", history_dir=history_dir, home=home,
        timestamp="2026-08-01T10:00:00",
    )

    [record] = history.list_history(history_dir)
    assert record.timestamp == "2026-08-01T10:00:00"


def test_write_manifest_uses_precomputed_entries_without_scanning(tmp_path):
    history_dir = tmp_path / "history"
    dest = tmp_path / "mabox-preserving-2026-08-17-1432.iso"
    precomputed = [history.HistoryEntry(name="Videos", type="dir", size_bytes=123)]

    # No `home` passed at all -- if write_manifest tried to scan, this would
    # raise via resolve_home_dir() (no SUDO_USER in the test environment).
    history.write_manifest(dest, "preserving", history_dir=history_dir, entries=precomputed)

    [record] = history.list_history(history_dir)
    assert record.entries == precomputed


def test_write_manifest_creates_history_dir_if_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "a" / "b" / "history"
    dest = tmp_path / "mabox-reset-2026-08.iso"

    history.write_manifest(dest, "reset", history_dir=history_dir, home=home)

    assert history_dir.is_dir()
    assert (history_dir / "mabox-reset-2026-08.toml").exists()


def test_write_manifest_uses_dest_stem_as_filename(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "history"

    history.write_manifest(tmp_path / "custom-name.iso", "preserving", history_dir=history_dir, home=home)

    assert (history_dir / "custom-name.toml").exists()


def test_write_manifest_falls_back_to_resolve_home_dir_when_home_omitted(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True)
    (home / "a.txt").write_bytes(b"x")
    monkeypatch.setattr(history.privilege, "resolve_home_dir", lambda: home)

    history_dir = tmp_path / "history"
    history.write_manifest(tmp_path / "x.iso", "preserving", history_dir=history_dir)

    [record] = history.list_history(history_dir)
    assert record.entries[0].name == "a.txt"


def test_list_history_returns_empty_list_when_dir_missing(tmp_path):
    assert history.list_history(tmp_path / "does-not-exist") == []


def test_list_history_sorted_oldest_first(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "history"
    # Filenames are deliberately in an order that would sort WRONG if
    # list_history() relied on filename order -- the day-first display
    # stamp (see cli.py) isn't lexicographically sortable across a month
    # boundary. Each manifest's own `timestamp` (ISO 8601, real
    # chronological order below) is what list_history() actually sorts by.
    fixtures = [
        ("mabox-preserving-01-09-2026-1000.iso", "2026-09-01T10:00:00"),
        ("mabox-preserving-15-08-2026-1200.iso", "2026-08-15T12:00:00"),
        ("mabox-preserving-17-08-2026-0900.iso", "2026-08-17T09:00:00"),
    ]
    for name, timestamp in fixtures:
        history.write_manifest(tmp_path / name, "preserving", history_dir=history_dir, home=home, timestamp=timestamp)

    records = history.list_history(history_dir)

    assert [r.iso for r in records] == [
        "mabox-preserving-15-08-2026-1200.iso",
        "mabox-preserving-17-08-2026-0900.iso",
        "mabox-preserving-01-09-2026-1000.iso",
    ]


def test_latest_returns_last_n_oldest_first(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "history"
    for i, name in enumerate(["a", "b", "c"]):
        history.write_manifest(
            tmp_path / f"{name}.iso", "preserving", history_dir=history_dir, home=home,
            timestamp=f"2026-08-{i + 1:02d}T00:00:00",
        )

    records = history.latest(2, history_dir)

    assert [r.iso for r in records] == ["b.iso", "c.iso"]


def test_latest_n_greater_than_available_returns_all(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "history"
    history.write_manifest(tmp_path / "a.iso", "preserving", history_dir=history_dir, home=home)

    assert len(history.latest(5, history_dir)) == 1


def test_latest_default_n_is_two(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    history_dir = tmp_path / "history"
    for i, name in enumerate(["a", "b", "c"]):
        history.write_manifest(
            tmp_path / f"{name}.iso", "preserving", history_dir=history_dir, home=home,
            timestamp=f"2026-08-{i + 1:02d}T00:00:00",
        )

    assert len(history.latest(history_dir=history_dir)) == 2


def test_latest_n_zero_or_negative_returns_empty(tmp_path):
    history_dir = tmp_path / "history"
    assert history.latest(0, history_dir) == []
    assert history.latest(-1, history_dir) == []
