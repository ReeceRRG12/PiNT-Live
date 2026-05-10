# -*- mode: python ; coding: utf-8 -*-
#
# PiNT Live — PyInstaller build spec
#
# Produces a single standalone Windows .exe with no Python install required.
#
# Run from the project root with:
#     python -m PyInstaller PiNT_Live.spec
#
# Output: dist/PiNT Live.exe

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Data files ─────────────────────────────────────────────────────────────
#
# customtkinter ships theme JSON files and images that it loads at runtime
# using __file__ — PyInstaller won't find them automatically.
customtkinter_datas = collect_data_files("customtkinter")

# ntc-templates ships TextFSM template files that netmiko uses for parsing.
ntc_templates_datas = collect_data_files("ntc_templates")

# Our own logo asset.  The dest folder "assets" matches what assets.py
# looks for relative to sys._MEIPASS when running frozen.
pint_live_datas = [
    ("pint_live/ui/assets/PiNT_InAppLogo.png", "assets"),
]

all_datas = customtkinter_datas + ntc_templates_datas + pint_live_datas

# ── Hidden imports ─────────────────────────────────────────────────────────
#
# netmiko loads device-type classes dynamically (e.g. ruckus_fastiron,
# cisco_ios) so PyInstaller can't detect them through static analysis.
# collect_submodules pulls them all in so every vendor works at runtime.
netmiko_hidden = collect_submodules("netmiko")

# ── Analysis ───────────────────────────────────────────────────────────────

a = Analysis(
    ["pint_live/main.py"],
    pathex=["."],
    binaries=[],
    datas=all_datas,
    hiddenimports=netmiko_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test frameworks and anything else we don't need at runtime
        "pytest", "unittest", "doctest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── Executable ─────────────────────────────────────────────────────────────

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PiNT Live",          # output filename: "PiNT Live.exe"
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                  # compress the exe if UPX is available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,             # no black console window behind the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
