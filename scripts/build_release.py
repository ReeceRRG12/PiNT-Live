"""Build and verify native release assets (Python 3.12 recommended).

    python -m pip install . "pyinstaller>=6.10,<7"
    python scripts/build_release.py --tag v0.7.0-beta.3

Windows produces a portable x64 EXE. macOS produces a DMG containing the
native .app and an Applications shortcut. Outputs live in dist/release/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import runpy
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version(tag: str) -> str:
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.(\d+))?", tag)
    if match is None:
        raise ValueError("Use a release tag such as v0.7.0-beta.3 or v0.7.0")
    version, channel, number = match.groups()
    return version + ({"alpha": "a", "beta": "b", "rc": "rc"}[channel] + number if channel else "")


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def checksum(asset: Path) -> Path:
    digest = hashlib.sha256()
    with asset.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    destination = asset.with_suffix(".sha256.txt")
    # macOS shasum treats CRLF's carriage return as part of the filename.
    destination.write_text(f"{digest.hexdigest()}  {asset.name}\n", encoding="ascii", newline="\n")
    return destination


def verify_windows_x64(executable: Path) -> None:
    with executable.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError("Windows executable has no DOS header")
        stream.seek(0x3C)
        pe_offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(pe_offset)
        if stream.read(6) != b"PE\0\0\x64\x86":
            raise RuntimeError("Windows executable is not an x64 PE binary")


def verify_macos_crypto() -> None:
    """Prevent colliding Python/cryptography OpenSSL dylibs in a frozen app."""
    from cryptography.hazmat.bindings import _rust

    linkage = subprocess.check_output(["otool", "-L", _rust.__file__], text=True)
    print("Cryptography native linkage:\n" + linkage, flush=True)
    if any(name in linkage for name in ("libssl.", "libcrypto.")):
        raise RuntimeError(
            "macOS release builds require statically linked cryptography. "
            "Install its binary wheel, or rebuild with OPENSSL_STATIC=1 and "
            "OPENSSL_DIR pointing to your OpenSSL installation (without pip's wheel cache)."
        )


def verify_frozen_app(executable: Path, report_path: Path, source_version: str) -> None:
    report_path.unlink(missing_ok=True)
    result = subprocess.run(
        [str(executable), "--smoke-test", str(report_path)], cwd=ROOT, timeout=90,
    )
    # Windowed apps have no console: print their report before raising for a
    # nonzero exit so CI logs expose the original startup/callback exception.
    if not report_path.is_file():
        raise RuntimeError(f"Frozen GUI exited {result.returncode} without a smoke report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print("Frozen GUI smoke report:\n" + json.dumps(report, indent=2), flush=True)
    result.check_returncode()
    if not report.get("ok") or report.get("version") != source_version:
        raise RuntimeError("Frozen application smoke check failed; see report above")


def build(tag: str) -> None:
    source_version = runpy.run_path(str(ROOT / "pint_live" / "__init__.py"))["__version__"]
    if package_version(tag) != source_version:
        raise ValueError(f"Tag {tag} does not match application version {source_version}")
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows" and machine in {"amd64", "x86_64"}:
        target = "Windows-x64"
    elif system == "Darwin" and machine in {"arm64", "x86_64"}:
        target = f"macOS-{'Apple-Silicon' if machine == 'arm64' else 'Intel'}"
    else:
        raise RuntimeError(f"Unsupported native build host: {system} {machine}")

    if system == "Darwin":
        verify_macos_crypto()
    run(sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "PiNT_Live.spec")
    output = ROOT / "dist" / "release"
    output.mkdir(parents=True, exist_ok=True)
    stem = f"PiNT-Live-{tag}-{target}"
    app = ROOT / "dist" / "PiNT Live.app"
    executable = (
        app / "Contents" / "MacOS" / "PiNT Live"
        if system == "Darwin" else ROOT / "dist" / "PiNT Live.exe"
    )

    if system == "Darwin":
        run("codesign", "--verify", "--deep", "--strict", str(app))
        actual_arch = subprocess.check_output(["lipo", "-archs", str(executable)], text=True).strip()
        if actual_arch != machine:
            raise RuntimeError(f"Expected {machine} executable, got {actual_arch}")
    else:
        verify_windows_x64(executable)

    report_path = ROOT / "build" / f"{stem}-smoke.json"
    verify_frozen_app(executable, report_path, source_version)

    if system == "Windows":
        asset = output / f"{stem}.exe"
        shutil.copy2(executable, asset)
    else:
        staging = ROOT / "build" / "dmg-staging"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        # ditto preserves the framework symlinks and signatures in a .app.
        run("ditto", str(app), str(staging / app.name))
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        asset = output / f"{stem}.dmg"
        asset.unlink(missing_ok=True)
        run("hdiutil", "create", "-volname", "PiNT Live", "-srcfolder", str(staging),
            "-ov", "-format", "UDZO", str(asset))
        run("hdiutil", "verify", str(asset))

    checksum_path = checksum(asset)
    print(f"Release asset: {asset}\nChecksum: {checksum_path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release tag matching the application version")
    build(parser.parse_args().tag)
