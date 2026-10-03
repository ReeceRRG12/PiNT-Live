# -*- mode: python ; coding: utf-8 -*-
"""Native Windows portable EXE and macOS .app builds.

Run scripts/build_release.py to build, smoke-test and package release assets.
PyInstaller must run on the target OS/architecture; it is not a cross-compiler.
"""

import runpy
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH)
version = runpy.run_path(str(root / "pint_live" / "__init__.py"))["__version__"]
logo = root / "pint_live" / "ui" / "assets" / "PiNT_InAppLogo.png"
is_macos = sys.platform == "darwin"

a = Analysis(
    [str(root / "scripts" / "desktop_entrypoint.py")],
    pathex=[str(root)],
    binaries=[],
    datas=(
        collect_data_files("customtkinter")
        + collect_data_files("ntc_templates")
        # ntc_templates and invoke read importlib.metadata at import time.
        # Include Netmiko's dependency metadata, including platform markers.
        + copy_metadata("netmiko", recursive=True)
        + [(str(logo), "pint_live/ui/assets")]
    ),
    hiddenimports=collect_submodules("netmiko"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "doctest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# macOS uses an onedir bundle: no extraction on every launch, and compatible
# with future Developer ID signing. Windows keeps the single-file workflow.
exe = EXE(
    pyz,
    a.scripts,
    [] if is_macos else a.binaries,
    [] if is_macos else a.datas,
    [],
    exclude_binaries=is_macos,
    name="PiNT Live",
    icon=str(logo),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if is_macos:
    coll = COLLECT(
        exe, a.binaries, a.datas,
        strip=False, upx=False, name="PiNT Live",
    )
    app = BUNDLE(
        coll,
        name="PiNT Live.app",
        icon=str(logo),
        bundle_identifier="com.pintlive.desktop",
        version=re.match(r"\d+\.\d+\.\d+", version).group(),
        info_plist={
            "CFBundleDisplayName": "PiNT Live",
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "NSLocalNetworkUsageDescription": (
                "PiNT Live connects to switches you select to read network data."
            ),
        },
    )
