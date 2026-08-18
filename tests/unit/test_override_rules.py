import pytest

from mabox_snapshot import excludes


def _mk(root, *rel_dirs):
    for rel in rel_dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)


def test_plain_exclude_passes_through_with_no_filesystem_access(tmp_path):
    # No paired include -- must not touch the filesystem at all, so a
    # nonexistent root is fine.
    rules = [excludes.OverrideRule("exclude", "home/*/Documents")]
    result = excludes.compile_override_rules(rules, root=tmp_path / "does-not-exist")
    assert result == ["home/*/Documents", "home/*/Documents/*"]


def test_protects_a_single_included_child(tmp_path):
    _mk(tmp_path, "home/alice/Documents/Custom_map", "home/alice/Documents/Other")
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert result == ["home/alice/Documents/Other"]


def test_protects_a_nested_grandchild(tmp_path):
    _mk(
        tmp_path,
        "home/alice/Documents/Custom_map/Nested/deep",
        "home/alice/Documents/Custom_map/OtherSibling",
        "home/alice/Documents/Other",
    )
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map/Nested"),
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert set(result) == {
        "home/alice/Documents/Other",
        "home/alice/Documents/Custom_map/OtherSibling",
    }
    # Never recursed into the protected leaf -- "deep" must not appear.
    assert "home/alice/Documents/Custom_map/Nested/deep" not in result


def test_protects_multiple_sibling_includes_under_one_exclude(tmp_path):
    _mk(
        tmp_path,
        "home/alice/Documents/A",
        "home/alice/Documents/B",
        "home/alice/Documents/C",
    )
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/A"),
        excludes.OverrideRule("include", "home/*/Documents/B"),
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert result == ["home/alice/Documents/C"]


def test_include_target_missing_on_disk_excludes_everything_present(tmp_path):
    _mk(tmp_path, "home/alice/Documents/Other")
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),  # doesn't exist
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert result == ["home/alice/Documents/Other"]


def test_exclude_target_missing_entirely_compiles_to_nothing(tmp_path):
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)  # no home/ dir at all
    assert result == []


def test_glob_exclude_expands_each_concrete_match_independently(tmp_path):
    _mk(
        tmp_path,
        "home/alice/Documents/Custom_map",
        "home/alice/Documents/Other",
        "home/bob/Documents/Custom_map",
        "home/bob/Documents/Private",
    )
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert set(result) == {"home/alice/Documents/Other", "home/bob/Documents/Private"}


def test_bare_include_with_no_enclosing_exclude_is_a_noop(tmp_path):
    _mk(tmp_path, "home/alice/Documents/Custom_map")
    rules = [excludes.OverrideRule("include", "home/*/Documents/Custom_map")]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert result == []
    assert excludes.find_orphan_includes(rules) == rules


def test_rejects_deeper_alternation(tmp_path):
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
        excludes.OverrideRule("exclude", "home/*/Documents/Custom_map/junk"),
    ]
    with pytest.raises(excludes.UnsupportedRuleNestingError):
        excludes.compile_override_rules(rules, root=tmp_path)


def test_rejects_glob_in_protected_suffix(tmp_path):
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_*"),
    ]
    with pytest.raises(ValueError):
        excludes.compile_override_rules(rules, root=tmp_path)


def test_unrelated_rule_pairs_dont_interfere(tmp_path):
    _mk(
        tmp_path,
        "home/alice/Documents/Custom_map",
        "home/alice/Documents/Other",
        "home/alice/Downloads/keep_this",
        "home/alice/Downloads/junk",
    )
    rules = [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
        excludes.OverrideRule("exclude", "home/*/Downloads"),
        excludes.OverrideRule("include", "home/*/Downloads/keep_this"),
    ]
    result = excludes.compile_override_rules(rules, root=tmp_path)
    assert set(result) == {"home/alice/Documents/Other", "home/alice/Downloads/junk"}


def test_override_rule_list_add_dedupes_and_persists(tmp_path):
    path = tmp_path / "overrides.list"
    rl = excludes.OverrideRuleList(path)
    rl.add("exclude", "home/*/Documents")
    rl.add("exclude", "home/*/Documents")
    rl.add("include", "home/*/Documents/Custom_map")

    assert rl.load() == [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
    ]


def test_override_rule_list_remove(tmp_path):
    path = tmp_path / "overrides.list"
    rl = excludes.OverrideRuleList(path)
    rl.add("exclude", "home/*/Documents")
    rl.add("include", "home/*/Documents/Custom_map")
    rl.remove("exclude", "home/*/Documents")

    assert rl.load() == [excludes.OverrideRule("include", "home/*/Documents/Custom_map")]


def test_override_rule_list_clear(tmp_path):
    path = tmp_path / "overrides.list"
    rl = excludes.OverrideRuleList(path)
    rl.add("exclude", "home/*/Documents")
    rl.clear()
    assert rl.load() == []


def test_override_rule_list_load_missing_file_returns_empty(tmp_path):
    assert excludes.OverrideRuleList(tmp_path / "nope").load() == []


def test_parse_rule_lines_rejects_bad_action():
    with pytest.raises(ValueError):
        excludes._parse_rule_lines("keep home/*/Documents\n")


def test_parse_rule_lines_skips_comments_and_blanks():
    text = "\n# comment\nexclude home/*/Documents\n\ninclude home/*/Documents/Custom_map\n"
    assert excludes._parse_rule_lines(text) == [
        excludes.OverrideRule("exclude", "home/*/Documents"),
        excludes.OverrideRule("include", "home/*/Documents/Custom_map"),
    ]
