import pytest

from mabox_snapshot import profiles


def test_resolve_returns_full_by_default_name():
    assert profiles.resolve("full") is profiles.FULL


def test_resolve_returns_lean():
    assert profiles.resolve("lean") is profiles.LEAN


def test_resolve_unknown_name_raises_with_choices():
    with pytest.raises(ValueError) as exc_info:
        profiles.resolve("bogus")
    assert "bogus" in str(exc_info.value)
    assert "full" in str(exc_info.value)
    assert "lean" in str(exc_info.value)


def test_full_profile_is_a_true_noop():
    assert profiles.FULL.extra_excludes == []
    assert profiles.FULL.trim_unselected_kernel_modules is False


def test_lean_profile_trims_kernel_modules():
    assert profiles.LEAN.trim_unselected_kernel_modules is True
    assert profiles.LEAN.extra_excludes  # non-empty
