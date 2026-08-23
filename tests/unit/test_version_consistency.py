"""Guards against version drift across the repo's package-version sources.

Nothing reads VERSION at runtime -- it exists purely as the canonical value
these files are expected to mirror. A mismatch here means a release bumped
one file and forgot another (pyproject.toml and __init__.py aren't in the
AUR release checklist, so they're the easiest to miss).

The man page doesn't carry a real version in its tracked source -- PKGBUILD
substitutes @VERSION@ with $pkgver at package time -- so it's checked for
the placeholder and the substitution wiring instead of an exact match."""

import re
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = (REPO_ROOT / "VERSION").read_text().strip()


def test_init_version_matches_version_file():
    from mabox_snapshot import __version__
    assert __version__ == CANONICAL


def test_pyproject_version_matches_version_file():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert data["project"]["version"] == CANONICAL


def test_pkgbuild_pkgver_matches_version_file():
    text = (REPO_ROOT / "packaging" / "PKGBUILD").read_text()
    match = re.search(r"^pkgver=(\S+)$", text, re.MULTILINE)
    assert match, "PKGBUILD has no pkgver= line"
    assert match.group(1) == CANONICAL


def test_man_page_carries_version_placeholder():
    text = (REPO_ROOT / "man" / "mabox-snapshot.1").read_text()
    assert '"mabox-snapshot @VERSION@"' in text, (
        "man page .TH line should carry the @VERSION@ placeholder, "
        "substituted by PKGBUILD at package time -- not a hardcoded version"
    )


def test_pkgbuild_substitutes_man_page_version_placeholder():
    text = (REPO_ROOT / "packaging" / "PKGBUILD").read_text()
    assert "@VERSION@" in text, (
        "PKGBUILD should sed the man page's @VERSION@ placeholder to "
        "$pkgver at package time"
    )
