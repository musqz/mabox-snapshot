from mabox_snapshot import packages


def test_split_foreign_packages_uses_injected_checker():
    def fake_checker(pkg: str) -> bool:
        return pkg in {"yay", "visual-studio-code-bin"}

    report = packages.split_foreign_packages(
        ["yay", "visual-studio-code-bin", "my-hand-built-thing"],
        is_aur_available=fake_checker,
    )

    assert report.aur_reproducible == ["yay", "visual-studio-code-bin"]
    assert report.local_only == ["my-hand-built-thing"]


def test_split_foreign_packages_empty_input_short_circuits():
    def fail(_pkg):
        raise AssertionError("should not be called for empty input")

    report = packages.split_foreign_packages([], is_aur_available=fail)

    assert report.aur_reproducible == []
    assert report.local_only == []


def test_copy_pacman_config_skips_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(packages.constants, "PACMAN_CONF", tmp_path / "does-not-exist.conf")
    monkeypatch.setattr(packages.constants, "PACMAN_MIRRORLIST", tmp_path / "does-not-exist-mirrorlist")

    dest_root = tmp_path / "overlay"
    packages.copy_pacman_config(dest_root)  # must not raise

    assert not (dest_root / "etc").exists()


def test_copy_pacman_config_copies_existing_files(tmp_path, monkeypatch):
    fake_conf = tmp_path / "pacman.conf"
    fake_conf.write_text("[options]\n")
    monkeypatch.setattr(packages.constants, "PACMAN_CONF", fake_conf)
    monkeypatch.setattr(packages.constants, "PACMAN_MIRRORLIST", tmp_path / "missing-mirrorlist")

    dest_root = tmp_path / "overlay"
    packages.copy_pacman_config(dest_root)

    copied = dest_root / fake_conf.relative_to("/")
    assert copied.read_text() == "[options]\n"
