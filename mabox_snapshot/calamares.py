"""Calamares installer integration.

Mostly a thin override layer: it comes straight from the calamares
package's own tested /usr/share/calamares/settings.conf + modules/*.conf,
already present in the squashed rootfs because calamares is an installed
package on the build host. A few targeted exceptions do touch the install
sequence itself, each one forced by a real install failure that traces
back to the same root cause: this config is written for a
freshly-pacstrapped rootfs, not a snapshot-of-a-running-system install
(see insert_live_source_job(), INITCPIO_CONF_OVERRIDE,
SERVICES_CONF_OVERRIDE, and insert_removeuser_job() below for each one's
specific story).

Branding is Mabox's own and static (see constants.CALAMARES_BRANDING_SRC
-- branding.desc, show.qml, and their images, the exact assets that
produce Mabox's real live-ISO install branding), applied in both modes --
reset mode writes it into the overlay layer (write_branding(), consumed
by overlay.py's build_overlay()), preserving mode has no overlay step to
write into so it goes in as mksquashfs pseudo-files straight into the
rootfs layer instead (build_branding_pseudo_specs(), consumed by cli.py
alongside seed.etc_skel_pseudo_specs() in the same pseudo-file list).
The one build-time-dynamic part is branding.desc's version strings: the
shipped file carries a "1.0" placeholder, rewritten from /etc/lsb-release
(DISTRIB_RELEASE + DISTRIB_CODENAME, e.g. "26.08 Istredd") by
render_branding_desc() -- Mabox's /etc/os-release has no version field at
all, and Calamares' own branding.desc substitution only reads os-release.
This used to be builder-configurable via a slide-*.png + branding.toml
pair under IMAGES_DIR, but this tool is Mabox-specific throughout
(DEMO_USERNAME, MISO_BASEDIR, ISO_VOLID, ...) and nobody had actually
configured one -- one fixed identity is simpler and more stable than a
template/config layer nobody used. Reset mode's demo account removal
(see insert_removeuser_job()) is reset-mode only and unconditional,
independent of branding -- preserving mode's snapshot never ran with a
synthetic demo account to remove.
"""

from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path

from . import constants


# branding.desc ships placeholder version strings ("1.0"); render_branding_desc()
# rewrites them from /etc/lsb-release at build time. Named here so that
# write_branding() (reset mode) and cli.py's preserving-mode path -- which
# renders into a workdir file, since it has no overlay to write into -- agree
# on the filename.
BRANDING_DESC_NAME = "branding.desc"


def calamares_installed(settings_file: Path = constants.CALAMARES_SETTINGS_FILE) -> bool:
    """Whether the calamares package is installed on the build host, detected
    by its own settings.conf -- the file both build modes read and layer
    Mabox's overrides onto (reset mode via write_settings_override(),
    preserving mode via cli.py's pseudo-spec block).

    calamares is an optdepend, not a dependency: it's the live-ISO installer,
    normally removed once Mabox itself is installed to disk, so most build
    hosts won't have it. When it's absent cli.py skips every Calamares
    config/branding step and builds a live-only ISO -- one that boots to a
    live session but carries no installer -- printing a clear notice rather
    than failing."""
    return settings_file.is_file()


def check_branding_installed(src_dir: Path = constants.CALAMARES_BRANDING_SRC) -> None:
    """Both build modes apply Mabox's own Calamares branding unconditionally
    (see write_branding() / build_branding_pseudo_specs()), reading it from
    src_dir -- a static asset the package installs at
    constants.CALAMARES_BRANDING_SRC. A stale or partial install can leave
    it missing (the rest of /usr/share/mabox-snapshot present, this one dir
    not), and without this check the build only trips over it deep inside
    cmd_create(), after the root prompt and workdir wipe, as a bare
    '[Errno 2] No such file or directory'. Fail early and say what to do.
    branding.desc specifically is required, not just "some file": it's the
    component's manifest -- without it Calamares falls back to its own
    default (non-Mabox, "1.0") branding, and both modes now read it directly
    to render the real version in (see render_branding_desc()), so a dir
    holding only the slideshow images is still a broken install."""
    if not src_dir.is_dir() or not (src_dir / BRANDING_DESC_NAME).is_file():
        raise FileNotFoundError(
            f"Mabox Calamares branding not found at {src_dir} (no {BRANDING_DESC_NAME}) -- is "
            "mabox-snapshot installed via its package? A stale or partial build can be missing "
            "this directory; reinstall the package to restore it"
        )


def lsb_release_versioned_name(lsb_release_text: str) -> str | None:
    """"<DISTRIB_RELEASE> <DISTRIB_CODENAME>" from /etc/lsb-release's contents
    -- e.g. "26.08 Istredd" -- or None if either field is missing. Mabox's
    /etc/os-release carries no version at all (ID=manjaro, BUILD_ID=rolling),
    and Calamares' branding.desc @{} substitution only reads os-release, so
    lsb-release is the only place the real release identity can come from.
    Equivalent to the awk one-liner
    `awk -F= '/DISTRIB_RELEASE=/{printf $2" "} /CODENAME/{print $2}'`."""
    fields = {}
    for line in lsb_release_text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    release = fields.get("DISTRIB_RELEASE")
    codename = fields.get("DISTRIB_CODENAME")
    if not release or not codename:
        return None
    return f"{release} {codename}"


def render_branding_desc(branding_desc_text: str, lsb_release_text: str) -> str:
    """Rewrites branding.desc's placeholder version strings from
    /etc/lsb-release's contents -- version/shortVersion become the bare
    "<release> <codename>", versionedName/shortVersionedName get the product
    name prepended. Returns the text unchanged if the release/codename can't
    be resolved (see lsb_release_versioned_name()) -- better the shipped
    placeholder than a half-filled "Mabox Linux " on the welcome page."""
    versioned = lsb_release_versioned_name(lsb_release_text)
    if versioned is None:
        return branding_desc_text
    values = {
        "version": versioned,
        "shortVersion": versioned,
        "versionedName": f"Mabox Linux {versioned}",
        "shortVersionedName": f"Mabox {versioned}",
    }
    for key, value in values.items():
        branding_desc_text = re.sub(
            rf"(?m)^([ \t]*{key}:[ \t]*).*$",
            lambda m, v=value: m.group(1) + v,
            branding_desc_text,
        )
    return branding_desc_text


def write_branding(
    overlay_dir: Path,
    src_dir: Path = constants.CALAMARES_BRANDING_SRC,
    lsb_release_file: Path = constants.LSB_RELEASE_FILE,
) -> None:
    """Copies Mabox's Calamares branding -- branding.desc, show.qml, and
    their slideshow/logo images -- into overlay_dir's branding component.
    branding.desc's placeholder version strings are rewritten from
    lsb_release_file first (see render_branding_desc()); every other file is
    copied verbatim. Reset mode only -- see build_branding_pseudo_specs() /
    cli.py for preserving mode's equivalent."""
    branding_dir = overlay_dir / "etc/calamares/branding" / constants.CALAMARES_BRANDING_COMPONENT
    branding_dir.mkdir(parents=True, exist_ok=True)
    lsb_release_text = lsb_release_file.read_text() if lsb_release_file.exists() else ""
    for item in src_dir.iterdir():
        if not item.is_file():
            continue
        if item.name == BRANDING_DESC_NAME:
            (branding_dir / item.name).write_text(render_branding_desc(item.read_text(), lsb_release_text))
        else:
            shutil.copy2(item, branding_dir / item.name)


# Not "etc/calamares/branding/mabox" itself declared as the sole dir entry
# below -- its own parent, etc/calamares/branding, isn't a real directory
# on a stock system either (same "Pathname does not exist in filesystem"
# constraint as unpackfs_pseudo_specs()'s leading two dir entries), so it
# needs its own pseudo-dir declaration too. etc/calamares itself doesn't,
# since unpackfs_pseudo_specs() always declares that one already.
BRANDING_TARGET_DIR = f"etc/calamares/branding/{constants.CALAMARES_BRANDING_COMPONENT}"


def build_branding_pseudo_specs(files: list[Path]) -> list[str]:
    """mksquashfs -p specs injecting Mabox's Calamares branding files
    directly into a squashed rootfs layer -- preserving mode's equivalent
    of write_branding(), which reset mode uses instead (no overlay step to
    write into here). files is the actual directory listing of
    constants.CALAMARES_BRANDING_SRC, gathered by the caller (see cli.py)
    rather than here, so this function stays pure and testable without
    touching the real filesystem -- except the caller swaps in a workdir
    copy of branding.desc with its version strings already rendered from
    /etc/lsb-release (see render_branding_desc()), keeping its
    BRANDING_DESC_NAME filename so the target path is unchanged."""
    specs = [
        "etc/calamares/branding d 755 0 0",
        f"{BRANDING_TARGET_DIR} d 755 0 0",
    ]
    for f in files:
        specs.append(f"{BRANDING_TARGET_DIR}/{f.name} f 644 0 0 cat {shlex.quote(str(f))}")
    return specs


def repoint_branding(settings_text: str) -> str:
    """Repoints settings.conf's 'branding:' line at Mabox's own component.
    Shared by write_settings_override() (reset mode) and cli.py's
    preserving-mode settings.conf construction -- both need it, but
    preserving mode's settings.conf isn't built via write_settings_override()
    (it has no overlay to write into, and doesn't want that function's
    unconditional insert_removeuser_job() -- preserving mode never had a
    demo account to remove)."""
    return re.sub(r"(?m)^branding:\s*\S+", f"branding: {constants.CALAMARES_BRANDING_COMPONENT}", settings_text)


# Target path Calamares reads settings.conf overrides from -- Calamares
# layers /etc/calamares/* on top of its /usr/share/calamares/* package
# defaults. Shared between write_settings_override() (reset-mode
# branding, written into the overlay layer) and build_unpackfs_conf's
# --encrypt path below (written via mksquashfs pseudo-file straight into
# the rootfs layer, since preserving mode has no overlay to write into).
SETTINGS_CONF_TARGET_PATH = "etc/calamares/settings.conf"


# Calamares' stock removeuser module (shipped, just never wired into the
# stock settings.conf's exec sequence -- confirmed present at
# /usr/share/calamares/modules/removeuser.conf on this host, defaulting
# to `username: live`, which does nothing on a mabox-snapshot ISO: reset
# mode's synthetic account is named "demo", not "live" -- see
# constants.DEMO_USERNAME/sanitize.py) userdel's a named account from the
# target. Without it, reset mode's demo/demo account -- meant only as a
# convenience login for the *live* "try before you install" session --
# survives untouched onto the installed system: confirmed against a real
# install, the freshly-created account and "demo" both work at the
# lightdm greeter after a completed install. Override removeuser.conf to
# target DEMO_USERNAME, and insert '- removeuser' into settings.conf's
# exec sequence (stock settings.conf never runs this module at all).
# Reset-mode only -- preserving mode is a personal clone of a real
# system, it was never running with a synthetic demo account to remove.
REMOVEUSER_CONF_TARGET_PATH = "etc/calamares/modules/removeuser.conf"
REMOVEUSER_CONF_OVERRIDE = f"username: {constants.DEMO_USERNAME}\n"


def insert_removeuser_job(settings_text: str) -> str:
    """Inserts '- removeuser' immediately after the last '- users' line
    in settings.conf. '- users' appears twice in the stock file (once in
    the show phase, once in exec) -- the last match is always the exec
    one, since Calamares' own sequence format requires exec to follow
    the show phase it consumes jobs from. Raises ValueError if no
    '- users' line exists at all -- fail loudly rather than silently
    produce a settings.conf that never removes reset mode's demo
    account."""
    matches = list(re.finditer(r"(?m)^([ \t]*)- users[ \t]*$", settings_text))
    if not matches:
        raise ValueError("settings.conf has no '- users' line -- can't insert the removeuser job")
    match = matches[-1]
    indent = match.group(1)
    line_end = match.end() + 1  # past '- users'' own trailing newline
    insertion = f"{indent}- removeuser\n"
    return settings_text[:line_end] + insertion + settings_text[line_end:]


def write_removeuser_override(overlay_dir: Path) -> None:
    dest = overlay_dir / REMOVEUSER_CONF_TARGET_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(REMOVEUSER_CONF_OVERRIDE)


def write_settings_override(overlay_dir: Path, source: Path = constants.CALAMARES_SETTINGS_FILE) -> None:
    """A copy of Calamares' own tested settings.conf, repointed at Mabox's
    own branding component (see write_branding() above -- always applied,
    reset mode has no stock-branding fallback path anymore) with
    '- removeuser' spliced into its exec sequence (see
    insert_removeuser_job() -- reset mode's only way to shed its demo
    account)."""
    text = repoint_branding(source.read_text())
    text = insert_removeuser_job(text)
    dest = overlay_dir / SETTINGS_CONF_TARGET_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)


# Same /etc override convention as write_settings_override's dest above --
# Calamares layers /etc/calamares/* on top of its /usr/share/calamares/*
# package defaults, so this never has to touch (or even confirm the
# existence of) the real /usr/share/calamares/modules/unpackfs.conf the
# installed calamares package ships. That stock file is written for
# Manjaro's own rootfs/desktopfs/mhwdfs three-layer split, assembled per
# ISO by manjaro-tools' buildiso -- a build pipeline this tool never runs.
# Left in place, it points unpackfs at squashfs sources that don't exist
# on a mabox-snapshot ISO, which is exactly what broke a real install
# ("Bad unpackfs configuration", confirmed booting a built ISO in QEMU).
UNPACKFS_CONF_PATH = "etc/calamares/modules/unpackfs.conf"

UNPACKFS_ENTRY_TEMPLATE = """    - source: "/run/miso/bootmnt/{basedir}/{arch}/{name}.sfs"
      sourcefs: "squashfs"
      destination: ""
"""

# --encrypt builds ship rootfs.sfs.luks instead of a plaintext rootfs.sfs --
# unpackfs's plain sourcefs: "squashfs" can't decrypt LUKS, so it can't read
# that file directly. The live boot hook (miso_luks) already decrypts it
# once, early in the initramfs, to build the live session's own root, but
# that mount (/run/miso/sfs/rootfs) doesn't survive switch_root -- and,
# verified the hard way in a real VM, a *second* mount made later at boot
# (the first fix attempt here, a systemd unit) isn't reliable either: it
# can go empty again well after boot, for reasons that were never fully
# pinned down, with no guarantee it's still populated by whenever Calamares
# actually gets run. The only mount that's provably still valid is one made
# *immediately* before it's read -- so build_unpackfs_conf()'s --encrypt
# path pairs sourcefs: "file" (verified against the installed calamares
# package: UnpackEntry.is_file() skips mounting entirely and rsyncs
# straight from source) with a shellprocess job (see
# build_shellprocess_remount_conf()/insert_live_source_job() below)
# injected immediately before unpackfs in Calamares' own exec sequence,
# so the remount and the read happen back to back with no gap for
# anything to disturb in between.
UNPACKFS_FILE_ENTRY_TEMPLATE = """    - source: "{path}"
      sourcefs: "file"
      destination: ""
"""

# Named module instance, per Calamares' own convention (confirmed against
# a real reference config on this host, ~/Github/penguins-eggs -- a
# similar Calamares-based remaster tool solving the same "run something
# in the live environment before the real install" problem): a
# `module@instanceId` sequence entry pairs with a
# `modules/module@instanceId.conf` file, literal '@' included.
SHELLPROCESS_INSTANCE_ID = "mabox-remount-live-source"
SHELLPROCESS_INSTANCE = f"shellprocess@{SHELLPROCESS_INSTANCE_ID}"
SHELLPROCESS_CONF_TARGET_PATH = f"etc/calamares/modules/{SHELLPROCESS_INSTANCE}.conf"

SHELLPROCESS_REMOUNT_CONF_TEMPLATE = """---
i18n:
    name: "Remounting decrypted rootfs for install..."

dontChroot: true
timeout: 30
script:
    - "mkdir -p {mount_point}"
    - "mountpoint -q {mount_point} || mount -o ro /dev/mapper/{mapper_name} {mount_point}"
"""


def build_shellprocess_remount_conf(
    mount_point: str = constants.MISO_LUKS_LIVE_ROOTFS_MOUNT,
    mapper_name: str = constants.ISO_LUKS_MAPPER_NAME,
) -> str:
    """dontChroot: true runs this in the live/host environment (the target
    doesn't exist yet at this point in the sequence). The mountpoint -q
    guard makes it idempotent -- a no-op if something already mounted it
    -- and, deliberately, the mount command has no leading '-': per
    shellprocess's own convention a command that isn't '-'-prefixed
    aborts the install on failure, which is exactly right here. Better a
    loud, immediate failure than silently unpacking an empty source."""
    return SHELLPROCESS_REMOUNT_CONF_TEMPLATE.format(mount_point=mount_point, mapper_name=mapper_name)


# Second named instance, same module@instanceId convention as the remount
# job above -- undoes it once unpackfs is done reading, instead of leaving
# /dev/mapper/{mapper_name} open for the rest of the exec sequence. Every
# later chroot-based job (grubcfg, bootloader, ...) runs with the live
# environment's /dev bind-mounted in, so an unrelated crypto device left
# open the whole time stays visible to grub-install/efibootmgr's own
# device enumeration inside the chroot -- a plausible explanation for a
# real, confirmed symptom: an --encrypt install that completed without
# error still produced no "Manjaro" UEFI boot entry at all, where the
# equivalent non-encrypt install did.
SHELLPROCESS_CLEANUP_INSTANCE_ID = "mabox-close-live-source"
SHELLPROCESS_CLEANUP_INSTANCE = f"shellprocess@{SHELLPROCESS_CLEANUP_INSTANCE_ID}"
SHELLPROCESS_CLEANUP_CONF_TARGET_PATH = f"etc/calamares/modules/{SHELLPROCESS_CLEANUP_INSTANCE}.conf"

SHELLPROCESS_CLEANUP_CONF_TEMPLATE = """---
i18n:
    name: "Releasing decrypted rootfs..."

dontChroot: true
timeout: 30
script:
    - "-umount {mount_point}"
    - "-cryptsetup close {mapper_name}"
"""


def build_shellprocess_cleanup_conf(
    mount_point: str = constants.MISO_LUKS_LIVE_ROOTFS_MOUNT,
    mapper_name: str = constants.ISO_LUKS_MAPPER_NAME,
) -> str:
    """Both commands are '-'-prefixed (best-effort, per shellprocess's own
    convention) -- this is cleanup after a successful unpack, not core
    functionality, and a merely-imperfect close (e.g. something
    unexpected still referencing it) shouldn't abort an otherwise-working
    install the way a failed remount rightly does."""
    return SHELLPROCESS_CLEANUP_CONF_TEMPLATE.format(mount_point=mount_point, mapper_name=mapper_name)


def insert_live_source_job(settings_text: str) -> str:
    """Inserts SHELLPROCESS_INSTANCE immediately before the '- unpackfs'
    line in settings.conf's exec sequence, and SHELLPROCESS_CLEANUP_INSTANCE
    immediately after it, preserving indentation -- remount right before
    the read, close right after, no gap either side. Both get declared in
    a top-level 'instances:' block -- confirmed via a real install this
    was the actual missing piece the whole time: a bare `module@id`
    reference in the exec sequence does not by itself register a module
    instance with Calamares (verified against a real install: the
    sequence entry landed correctly, the module's own .conf file was
    present and well-formed, and the job still never ran -- no
    /run/mabox-snapshot directory was ever created, not even the empty
    one 'mkdir -p' would leave behind on a mount failure). Confirmed by
    re-checking the reference config this mechanism was modeled on,
    ~/Github/penguins-eggs's own settings.conf: it declares an explicit
    'instances:' entry (id/module/config) for each of its own named
    shellprocess jobs -- that block is what actually tells Calamares an
    instance exists at all; the exec sequence entry only orders it
    relative to other jobs. Raises ValueError if the '- unpackfs' anchor
    or the top-level 'sequence:' key isn't found -- fail loudly if
    Calamares' upstream settings.conf format ever changes unexpectedly,
    rather than silently produce a settings.conf that never runs these
    jobs at all."""
    match = re.search(r"(?m)^([ \t]*)- unpackfs[ \t]*$", settings_text)
    if match is None:
        raise ValueError("settings.conf has no '- unpackfs' line in its exec sequence -- can't insert the remount job")
    indent = match.group(1)
    line_end = match.end() + 1  # past '- unpackfs''s own trailing newline
    text = (
        settings_text[: match.start()]
        + f"{indent}- {SHELLPROCESS_INSTANCE}\n"
        + settings_text[match.start() : line_end]
        + f"{indent}- {SHELLPROCESS_CLEANUP_INSTANCE}\n"
        + settings_text[line_end:]
    )

    sequence_match = re.search(r"(?m)^sequence:[ \t]*$", text)
    if sequence_match is None:
        raise ValueError("settings.conf has no top-level 'sequence:' key -- can't declare the remount job's instance")
    instances_block = (
        "instances:\n"
        f"  - id: {SHELLPROCESS_INSTANCE_ID}\n"
        "    module: shellprocess\n"
        f"    config: {SHELLPROCESS_INSTANCE}.conf\n\n"
        f"  - id: {SHELLPROCESS_CLEANUP_INSTANCE_ID}\n"
        "    module: shellprocess\n"
        f"    config: {SHELLPROCESS_CLEANUP_INSTANCE}.conf\n\n"
    )
    return text[: sequence_match.start()] + instances_block + text[sequence_match.start() :]


def remove_users_step(settings_text: str) -> str:
    """Removes every '- users' line from settings.conf -- both the one in
    the show phase's page list and the one in the exec phase's job list.
    Preserving mode's snapshot already contains a real, working account
    with its own real password, making Calamares' account-creation step
    redundant at best -- and actively harmful at worst: confirmed via a
    real install, typing the same username as the account already in the
    snapshot makes 'useradd' hard-abort, and since 'users' runs *before*
    grubcfg/bootloader in Calamares' own exec sequence, that abort skips
    bootloader installation entirely without any obvious sign why -- the
    install reports failure, but Calamares still lets the install proceed
    to a reboot into a half-finished, unbootable disk. Typing a different
    username avoids the abort but creates a second, broken-desktop account
    (see seed.etc_skel_pseudo_specs()). Simplest fix: never offer account
    creation at all for a mode whose entire premise is "this is already
    your account". Raises ValueError if no '- users' line is found at all
    -- fail loudly if Calamares' upstream settings.conf format ever
    changes unexpectedly, rather than silently leave the step in place."""
    matches = list(re.finditer(r"(?m)^[ \t]*- users[ \t]*$\n?", settings_text))
    if not matches:
        raise ValueError("settings.conf has no '- users' line -- can't remove the account-creation step")
    result = settings_text
    for match in reversed(matches):
        result = result[: match.start()] + result[match.end() :]
    return result


# Calamares' stock initcpio.conf hardcodes `kernel: linux` -- after
# install it regenerates the initramfs on the target for a preset
# literally named "linux" (/etc/mkinitcpio.d/linux.preset). Mabox uses
# versioned kernel packages instead (e.g. linux618, see kernels.py), so a
# preserving-mode snapshot's target only ever has linux618.preset, never
# a plain linux.preset -- confirmed against a real install ("Failed to
# load preset: '/etc/mkinitcpio.d/linux.preset'"). "all" is a documented
# valid value (see the stock file's own comments): it regenerates every
# preset actually present on the target instead of one hardcoded name --
# this also fixes a latent bug for --all-kernels builds, which would
# otherwise only ever get one (nonexistent) kernel's initramfs
# regenerated by Calamares post-install. Applies to both modes
# unconditionally, unlike the settings.conf/shellprocess pair above --
# this isn't encrypt-specific, and it's static content (no per-build
# parameters), so it's injected the same way UNPACKFS_CONF_PATH already
# is for every build.
INITCPIO_CONF_TARGET_PATH = "etc/calamares/modules/initcpio.conf"
INITCPIO_CONF_OVERRIDE = "kernel: all\nbe_unsafe: false\n"


# Manjaro's stock services.conf marks the "graphical" unit enable
# mandatory: true -- confirmed against a real install ("Cannot enable
# systemd unit graphical. systemctl enable call in chroot returned error
# code 1", the whole install aborts, no Calamares.log ever written to
# find the real systemctl stderr). The blanket graphical.target enable is
# redundant on top of the dedicated displaymanager module (already
# further down Calamares' own exec sequence, and the thing that actually
# configures/enables the login manager) -- it's a belt-and-braces default
# that makes sense for a freshly-pacstrapped rootfs, not a
# snapshot-of-a-running-system install. Preserving mode carries over the
# live ISO's own systemd on-disk state (whatever masks/symlinks its own
# autologin desktop session uses), which this offline `systemctl enable`
# chokes on in a way a fresh install never would -- same pattern as the
# initcpio.conf bug above: harmless on a normal Manjaro ISO, fatal
# against a snapshotted live system. Fix: override services.conf, keep
# NetworkManager (mandatory -- needed for networking on first boot) and
# pacman-init masking (Arch-specific correctness) exactly as shipped,
# drop the graphical entry entirely. Applies to both modes
# unconditionally, same reasoning as INITCPIO_CONF_OVERRIDE above.
SERVICES_CONF_TARGET_PATH = "etc/calamares/modules/services.conf"
SERVICES_CONF_OVERRIDE = (
    "units:\n"
    '  - name: "NetworkManager"\n'
    '    action: "enable"\n'
    "    mandatory: true\n"
    "\n"
    '  - name: "org.cups.cupsd"\n'
    '    action: "enable"\n'
    "\n"
    '  - name: "pacman-init"\n'
    '    action: "mask"\n'
)


# Calamares' own grubcfg *module* (unrelated to this project's grubcfg.py,
# which only builds the live ISO's boot menu -- this is the module that
# configures the INSTALLED target's /etc/default/grub). Per its stock
# /usr/share/calamares/modules/grubcfg.conf's own docs, it unconditionally
# recalculates GRUB_DISTRIBUTOR from the active Calamares branding
# component's bootloaderEntryName whenever keep_distributor is false (the
# stock default) -- it does NOT preserve whatever's already in the
# target's own /etc/default/grub. Confirmed on this host: a real Mabox
# system already ships GRUB_DISTRIBUTOR='Mabox' correctly on its own, but
# preserving mode never applies any branding at all (see write_branding()
# -- reset-mode only), so it stays on Calamares' stock 'manjaro' component,
# whose branding.desc sets bootloaderEntryName: Manjaro -- grubcfg clobbers
# the already-correct value with "Manjaro" there regardless. Confirmed
# against a real install: booting the resulting VM showed "*Manjaro Linux"
# / "Advanced options for Manjaro Linux" in GRUB despite the source
# system's own /etc/default/grub being correct all along. Applied to both
# modes uniformly below since it's a no-op, not a conflict, for reset
# mode's own Mabox branding.desc (bootloaderEntryName: Mabox already).
# keep_distributor: true stops grubcfg from touching GRUB_DISTRIBUTOR at
# all, so the install just carries over whatever the snapshot already has
# -- correct unconditionally, independent of mode or whether custom
# Calamares branding is ever configured. The rest of this override
# reproduces the stock file's other settings unchanged (verified against
# the installed calamares package on this host), same "keep everything
# except the one broken setting" approach as SERVICES_CONF_OVERRIDE above.
GRUBCFG_CONF_TARGET_PATH = "etc/calamares/modules/grubcfg.conf"
GRUBCFG_CONF_OVERRIDE = (
    "overwrite: false\n"
    "prefer_grub_d: false\n"
    "keep_distributor: true\n"
    'kernel_params: [ "quiet" ]\n'
    "defaults:\n"
    "    GRUB_TIMEOUT: 5\n"
    '    GRUB_DEFAULT: "saved"\n'
    "    GRUB_DISABLE_SUBMENU: true\n"
    '    GRUB_TERMINAL_OUTPUT: "console"\n'
    "    GRUB_DISABLE_RECOVERY: true\n"
    "always_use_defaults: false\n"
)


def build_unpackfs_conf(
    layer_names: list[str],
    basedir: str = constants.MISO_BASEDIR,
    arch: str = constants.ISO_ARCH,
    encrypt: bool = False,
) -> str:
    """One entry per squashfs layer this specific build actually produces
    (see overlay.py's BuildPlan -- ["rootfs"] in preserving mode,
    ["rootfs", "desktopfs"] in reset mode). Normally each entry reads the
    ISO's own on-media squashfs at the path the miso boot hook mounts the
    boot medium at. For an --encrypt build (rootfs.sfs.luks, preserving
    mode only), the "rootfs" entry instead reads the live session's
    already-decrypted mount (see UNPACKFS_FILE_ENTRY_TEMPLATE) -- every
    other layer name is unaffected."""
    entries = []
    for name in layer_names:
        if encrypt and name == "rootfs":
            entries.append(UNPACKFS_FILE_ENTRY_TEMPLATE.format(path=constants.MISO_LUKS_LIVE_ROOTFS_MOUNT))
        else:
            entries.append(UNPACKFS_ENTRY_TEMPLATE.format(basedir=basedir, arch=arch, name=name))
    return f"unpack:\n{''.join(entries)}"


def unpackfs_pseudo_specs(
    conf_path: Path,
    initcpio_conf_path: Path,
    services_conf_path: Path,
    grubcfg_conf_path: Path,
    encrypt: bool = False,
    settings_conf_path: Path | None = None,
    shellprocess_conf_path: Path | None = None,
    shellprocess_cleanup_conf_path: Path | None = None,
) -> list[str]:
    """mksquashfs -p specs injecting conf_path's contents (written by the
    caller from build_unpackfs_conf()) at UNPACKFS_CONF_PATH,
    initcpio_conf_path's contents (INITCPIO_CONF_OVERRIDE, written
    verbatim by the caller) at INITCPIO_CONF_TARGET_PATH,
    services_conf_path's contents (SERVICES_CONF_OVERRIDE, written
    verbatim by the caller) at SERVICES_CONF_TARGET_PATH, and
    grubcfg_conf_path's contents (GRUBCFG_CONF_OVERRIDE, written verbatim
    by the caller) at GRUBCFG_CONF_TARGET_PATH, inside the squashed
    rootfs layer. The leading two dir entries are required, not
    cosmetic -- verified empirically: mksquashfs's -p file spec fails
    outright ('Pathname "etc" does not exist in filesystem') unless its
    parent dirs are already real, and /etc/calamares/ (an admin-override
    path Calamares only optionally reads) usually isn't, even on a host
    with calamares itself installed. Declaring them as pseudo-dirs works
    whether or not the real dir already exists (also verified). The
    caller must also exclude all four target paths from the layer's own
    source scan (see cli.py) -- if a real file already sits there,
    mksquashfs silently keeps it over the pseudo-file instead.

    settings_conf_path, when given, additionally injects a modified
    settings.conf at SETTINGS_CONF_TARGET_PATH -- reusing the same two
    pseudo-dirs above. Passed whenever plan.mode == "preserving" (see
    cli.py): every preserving-mode build now needs its own settings.conf,
    at minimum to remove the '- users' step (see remove_users_step() --
    preserving mode's snapshot already has a real account, so Calamares'
    own account-creation step is redundant and, on a username collision,
    install-aborting). encrypt=True additionally splices the remount and
    cleanup jobs into that same settings.conf's exec sequence (see
    insert_live_source_job()) and injects both jobs' own module configs
    (see build_shellprocess_remount_conf()/build_shellprocess_cleanup_conf())
    -- callers must then also pass shellprocess_conf_path/
    shellprocess_cleanup_conf_path. Callers must exclude every target path
    actually injected from the layer's own source scan (see cli.py), same
    reasoning as UNPACKFS_CONF_PATH -- if a real file already sits there,
    mksquashfs silently keeps it over the pseudo-file instead. There's no
    permanent, on-disk file to generate these from: preserving mode has no
    overlay step to write into (that's reset-mode only), and writing
    straight to the *build host's own* /etc/calamares would mean
    permanently altering the machine's real installer config just to
    build a snapshot."""
    specs = [
        "etc/calamares d 755 0 0",
        "etc/calamares/modules d 755 0 0",
        f"{UNPACKFS_CONF_PATH} f 644 0 0 cat {shlex.quote(str(conf_path))}",
        f"{INITCPIO_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(initcpio_conf_path))}",
        f"{SERVICES_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(services_conf_path))}",
        f"{GRUBCFG_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(grubcfg_conf_path))}",
    ]
    if settings_conf_path is not None:
        specs.append(f"{SETTINGS_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(settings_conf_path))}")
    if encrypt:
        specs.append(f"{SHELLPROCESS_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(shellprocess_conf_path))}")
        specs.append(
            f"{SHELLPROCESS_CLEANUP_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(shellprocess_cleanup_conf_path))}"
        )
    return specs
