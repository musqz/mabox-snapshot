"""Calamares installer integration -- a thin branding overlay only.

The install sequence itself (partition/bootloader/users/mount/...) is
never touched: it comes straight from the calamares package's own tested
/usr/share/calamares/settings.conf + modules/*.conf, already present in
the squashed rootfs because calamares is an installed package on the
build host (verified: git.maboxlinux.org has no Mabox-specific Calamares
repo -- Mabox installs just inherit stock Manjaro branding/config unless
this tool overrides it).

Custom branding is entirely optional and reset-mode only (the "share
this with someone else" mode -- preserving mode is a personal clone, not
something that needs a welcome screen). With no images/branding.toml
configured, build_calamares_branding() does nothing and Calamares shows
its stock Manjaro branding.
"""

from __future__ import annotations

import re
import shlex
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import constants


@dataclass
class Slide:
    image: str  # filename relative to the images dir, e.g. "slide-0.png"
    head: str = ""
    body: str = ""


@dataclass
class BrandingConfig:
    product_name: str = constants.DEFAULT_CALAMARES_PRODUCT_NAME
    radius: int = constants.DEFAULT_TEXT_RADIUS
    slides: list[Slide] = field(default_factory=list)


def load_branding(images_dir: Path = constants.IMAGES_DIR) -> BrandingConfig | None:
    """None means no custom branding is configured -- the caller should
    skip the branding step entirely and let Calamares use its stock
    Manjaro branding, which is already present via the installed package."""
    slide_images = sorted(images_dir.glob("slide-*.png"))
    if not slide_images:
        return None

    toml_path = images_dir / "branding.toml"
    raw = {}
    if toml_path.exists():
        with toml_path.open("rb") as f:
            raw = tomllib.load(f)

    slide_texts = raw.get("slide", {})
    slides = []
    for image_path in slide_images:
        index = image_path.stem.split("-", 1)[1]  # "slide-3.png" -> "3"
        text = slide_texts.get(index, {})
        slides.append(Slide(image=image_path.name, head=text.get("head", ""), body=text.get("body", "")))

    return BrandingConfig(
        product_name=raw.get("product_name", constants.DEFAULT_CALAMARES_PRODUCT_NAME),
        radius=raw.get("radius", constants.DEFAULT_TEXT_RADIUS),
        slides=slides,
    )


def _yaml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


BRANDING_DESC_TEMPLATE = """---
componentName: {component}

welcomeStyleCalamares: false
welcomeExpandingLogo: true

windowExpanding: normal
windowSize: 800px,520px
windowPlacement: center

sidebar: qml
navigation: widget

strings:
    productName: {product_name}
    shortProductName: {short_product_name}
    version: "1.0"
    shortVersion: "1.0"
    versionedName: {versioned_name}
    shortVersionedName: {short_versioned_name}
    bootloaderEntryName: {short_product_name}
    productUrl: "https://maboxlinux.org/"
    supportUrl: "https://maboxlinux.org/"
    knownIssuesUrl: "https://maboxlinux.org/"
    releaseNotesUrl: "https://maboxlinux.org/"
    donateUrl: "https://maboxlinux.org/"

images:
    productIcon: "logo.svg"
    productLogo: "logo.svg"

style:
   SidebarBackground: "#263238"
   SidebarText: "#efefef"
   SidebarTextSelect: "#4d915e"
   SidebarTextHighlight: "#1a1c1b"

slideshow: "show.qml"
slideshowAPI: 2
"""


def build_branding_desc(branding: BrandingConfig) -> str:
    short_name = branding.product_name.split()[0] if branding.product_name.split() else branding.product_name
    return BRANDING_DESC_TEMPLATE.format(
        component=constants.CALAMARES_BRANDING_COMPONENT,
        product_name=_yaml_string(branding.product_name),
        short_product_name=_yaml_string(short_name),
        versioned_name=_yaml_string(f"{branding.product_name} 1.0"),
        short_versioned_name=_yaml_string(f"{short_name} 1.0"),
    )


SHOW_QML_TEMPLATE = """import QtQuick 2.15

Item {{
    id: root
    width: 800
    height: 400

    property int index: 0
    property var slides: [
{slides}
    ]

    function onActivate() {{ timer.restart(); index = 0; }}
    function onLeave() {{}}

    Timer {{
        id: timer
        interval: 6000
        running: false
        repeat: true
        onTriggered: index = (index + 1) % slides.length
    }}

    Image {{
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        source: slides.length > 0 ? slides[index].image : ""
    }}

    Rectangle {{
        visible: slides.length > 0 && (slides[index].head.length > 0 || slides[index].body.length > 0)
        color: "#000000"
        opacity: 0.55
        radius: {radius}
        anchors {{ left: parent.left; right: parent.right; bottom: parent.bottom; margins: 24 }}
        height: textColumn.implicitHeight + 32

        Column {{
            id: textColumn
            anchors {{ left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }}
            spacing: 6

            Text {{
                text: slides.length > 0 ? slides[index].head : ""
                color: "white"
                font.pixelSize: 22
                font.bold: true
                wrapMode: Text.WordWrap
                width: parent.width
            }}
            Text {{
                text: slides.length > 0 ? slides[index].body : ""
                color: "white"
                font.pixelSize: 15
                wrapMode: Text.WordWrap
                width: parent.width
            }}
        }}
    }}
}}
"""


def _qml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_show_qml(branding: BrandingConfig) -> str:
    slide_lines = [
        f"        {{ image: {_qml_string(s.image)}, head: {_qml_string(s.head)}, body: {_qml_string(s.body)} }},"
        for s in branding.slides
    ]
    return SHOW_QML_TEMPLATE.format(slides="\n".join(slide_lines), radius=branding.radius)


# Target path Calamares reads settings.conf overrides from -- Calamares
# layers /etc/calamares/* on top of its /usr/share/calamares/* package
# defaults. Shared between write_settings_override() (reset-mode
# branding, written into the overlay layer) and build_unpackfs_conf's
# --encrypt path below (written via mksquashfs pseudo-file straight into
# the rootfs layer, since preserving mode has no overlay to write into).
SETTINGS_CONF_TARGET_PATH = "etc/calamares/settings.conf"


def write_settings_override(overlay_dir: Path, source: Path = constants.CALAMARES_SETTINGS_FILE) -> None:
    """A copy of Calamares' own tested settings.conf with only the
    'branding:' line repointed at the mabox component -- the install
    sequence itself is never touched."""
    text = source.read_text()
    new_text = re.sub(r"(?m)^branding:\s*\S+", f"branding: {constants.CALAMARES_BRANDING_COMPONENT}", text)
    dest = overlay_dir / SETTINGS_CONF_TARGET_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(new_text)


def write_branding(overlay_dir: Path, branding: BrandingConfig, images_dir: Path = constants.IMAGES_DIR) -> None:
    branding_dir = overlay_dir / "etc/calamares/branding" / constants.CALAMARES_BRANDING_COMPONENT
    branding_dir.mkdir(parents=True, exist_ok=True)

    for slide in branding.slides:
        shutil.copy2(images_dir / slide.image, branding_dir / slide.image)

    if constants.MABOX_LOGO_SVG.exists():
        shutil.copy2(constants.MABOX_LOGO_SVG, branding_dir / "logo.svg")

    (branding_dir / "branding.desc").write_text(build_branding_desc(branding))
    (branding_dir / "show.qml").write_text(build_show_qml(branding))


def build_calamares_branding(overlay_dir: Path, images_dir: Path = constants.IMAGES_DIR) -> bool:
    """Returns True if custom branding was applied, False if skipped (no
    images configured -- Calamares falls back to its stock branding)."""
    branding = load_branding(images_dir)
    if branding is None:
        return False
    write_branding(overlay_dir, branding, images_dir)
    write_settings_override(overlay_dir)
    return True


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
SHELLPROCESS_INSTANCE = "shellprocess@mabox-remount-live-source"
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


def insert_live_source_job(settings_text: str) -> str:
    """Inserts SHELLPROCESS_INSTANCE immediately before the '- unpackfs'
    line in settings.conf's exec sequence, preserving its exact
    indentation. Raises ValueError if that anchor line isn't found --
    fail loudly if Calamares' upstream settings.conf format ever changes
    unexpectedly, rather than silently produce a settings.conf that never
    runs the remount job at all."""
    match = re.search(r"(?m)^([ \t]*)- unpackfs[ \t]*$", settings_text)
    if match is None:
        raise ValueError("settings.conf has no '- unpackfs' line in its exec sequence -- can't insert the remount job")
    indent = match.group(1)
    insertion = f"{indent}- {SHELLPROCESS_INSTANCE}\n"
    return settings_text[: match.start()] + insertion + settings_text[match.start() :]


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
    encrypt: bool = False,
    settings_conf_path: Path | None = None,
    shellprocess_conf_path: Path | None = None,
) -> list[str]:
    """mksquashfs -p specs injecting conf_path's contents (written by the
    caller from build_unpackfs_conf()) at UNPACKFS_CONF_PATH, and
    initcpio_conf_path's contents (INITCPIO_CONF_OVERRIDE, written
    verbatim by the caller) at INITCPIO_CONF_TARGET_PATH, inside the
    squashed rootfs layer. The leading two dir entries are required, not
    cosmetic -- verified empirically: mksquashfs's -p file spec fails
    outright ('Pathname "etc" does not exist in filesystem') unless its
    parent dirs are already real, and /etc/calamares/ (an admin-override
    path Calamares only optionally reads) usually isn't, even on a host
    with calamares itself installed. Declaring them as pseudo-dirs works
    whether or not the real dir already exists (also verified). The
    caller must also exclude both target paths from the layer's own
    source scan (see cli.py) -- if a real file already sits there,
    mksquashfs silently keeps it over the pseudo-file instead.

    encrypt=True additionally injects a modified settings.conf (with the
    remount job spliced into its exec sequence, see
    insert_live_source_job()) and the remount job's own module config
    (see build_shellprocess_remount_conf()) -- reusing the same two
    pseudo-dirs above, since both new files live under them too. Callers
    must pass settings_conf_path/shellprocess_conf_path (and exclude both
    their target paths from the layer's own source scan, same reasoning
    as UNPACKFS_CONF_PATH) whenever encrypt=True. There's no permanent,
    on-disk file to generate these from: preserving mode has no overlay
    step to write into (that's reset-mode only), and writing straight to
    the *build host's own* /etc/calamares would mean permanently altering
    the machine's real installer config just to build a snapshot."""
    specs = [
        "etc/calamares d 755 0 0",
        "etc/calamares/modules d 755 0 0",
        f"{UNPACKFS_CONF_PATH} f 644 0 0 cat {shlex.quote(str(conf_path))}",
        f"{INITCPIO_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(initcpio_conf_path))}",
    ]
    if encrypt:
        specs.append(f"{SETTINGS_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(settings_conf_path))}")
        specs.append(f"{SHELLPROCESS_CONF_TARGET_PATH} f 644 0 0 cat {shlex.quote(str(shellprocess_conf_path))}")
    return specs
