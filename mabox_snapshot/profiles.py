"""Named snapshot size/completeness tiers -- orthogonal to mode (which
controls privacy scope: whose data ships, real vs synthetic). --profile
controls how much of the data mode says should ship actually does.
Exactly two tiers for now (YAGNI) -- trivially extendable later without
redesign.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str
    extra_excludes: list[str] = field(default_factory=list)
    trim_unselected_kernel_modules: bool = False


FULL = Profile(name="full")  # today's behavior, unchanged -- must stay a true no-op

# VM images and container storage can hold irreplaceable, hand-configured
# local state, unlike a Steam game install (provably regenerable from
# Valve's CDN, already a universal default in configs/excludes.list.default)
# -- opt-in via --profile lean only, never a blanket default.
LEAN = Profile(
    name="lean",
    extra_excludes=[
        "home/*/VirtualBox VMs/*",
        "var/lib/libvirt/images/*",
        "var/lib/docker/*",
        "home/*/.local/share/containers/storage/*",
    ],
    trim_unselected_kernel_modules=True,
)

PROFILES = {p.name: p for p in (FULL, LEAN)}


def resolve(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError:
        choices = ", ".join(sorted(PROFILES))
        raise ValueError(f"unknown profile: {name!r} (choices: {choices})") from None
