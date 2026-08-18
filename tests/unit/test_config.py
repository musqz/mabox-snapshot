from pathlib import Path

from mabox_snapshot import config


def test_load_defaults_when_no_files_exist(tmp_path):
    cfg = config.load(system_path=tmp_path / "system.conf", user_path=tmp_path / "user.conf")
    assert cfg.compression == "zstd"
    assert cfg.workdir == config.SnapshotConfig().workdir
    assert cfg.profile == "full"


def test_load_coerces_profile_field(tmp_path):
    system = tmp_path / "system.conf"
    system.write_text('profile = "lean"\n')

    cfg = config.load(system_path=system, user_path=tmp_path / "user.conf")
    assert cfg.profile == "lean"


def test_user_config_overrides_system_config(tmp_path):
    system = tmp_path / "system.conf"
    user = tmp_path / "user.conf"
    system.write_text('compression = "xz"\n')
    user.write_text('compression = "lz4"\n')

    cfg = config.load(system_path=system, user_path=user)
    assert cfg.compression == "lz4"


def test_load_rejects_unknown_key(tmp_path):
    system = tmp_path / "system.conf"
    system.write_text('nonsense_key = "x"\n')

    try:
        config.load(system_path=system, user_path=tmp_path / "user.conf")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "nonsense_key" in str(e)


def test_load_coerces_path_and_tuple_fields(tmp_path):
    system = tmp_path / "system.conf"
    system.write_text('workdir = "/tmp/somewhere"\nexclude_folders = ["Videos", "Downloads"]\n')

    cfg = config.load(system_path=system, user_path=tmp_path / "user.conf")
    assert cfg.workdir == Path("/tmp/somewhere")
    assert cfg.exclude_folders == ("Videos", "Downloads")


def test_load_float_field_needs_no_coercion(tmp_path):
    system = tmp_path / "system.conf"
    system.write_text("splash_border_fraction = 0.1\n")

    cfg = config.load(system_path=system, user_path=tmp_path / "user.conf")
    assert cfg.splash_border_fraction == 0.1


def test_set_value_inserts_new_key(tmp_path):
    user = tmp_path / "user.conf"
    config.set_value("compression", "xz", user_path=user)

    assert 'compression = "xz"' in user.read_text()


def test_set_value_replaces_existing_key_without_duplicating(tmp_path):
    user = tmp_path / "user.conf"
    config.set_value("compression", "xz", user_path=user)
    config.set_value("compression", "lz4", user_path=user)

    content = user.read_text()
    assert content.count("compression") == 1
    assert 'compression = "lz4"' in content


def test_set_value_rejects_unknown_key(tmp_path):
    user = tmp_path / "user.conf"
    try:
        config.set_value("nope", "x", user_path=user)
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert not user.exists()
