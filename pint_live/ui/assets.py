"""
PiNT Live — asset loading helpers.

Handles image loading from the `assets/` folder and sets the
taskbar icon, with full support for PyInstaller frozen builds.
"""

import sys
import tempfile
from pathlib import Path
from tkinter import PhotoImage, TclError
from typing import Optional

import customtkinter as ctk


def base_path() -> str:
    """Return the package directory in source and current PyInstaller builds."""
    return str(Path(__file__).resolve().parent)


def asset_path(filename: str, subfolder: str = "assets") -> Path:
    """Locate package assets, also supporting the old bundle's flat layout."""
    packaged = Path(base_path()) / subfolder / filename
    if packaged.is_file():
        return packaged
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        legacy = Path(bundle) / subfolder / filename
        if legacy.is_file():
            return legacy
    return packaged


def _read_image(filename: str, subfolder: str):
    from PIL import Image

    # Detach image data from the file so bundled handles are closed promptly.
    # Keep the original pixels: CTkImage creates its own DPI-specific rasters.
    with Image.open(asset_path(filename, subfolder)) as source:
        return source.convert("RGBA")


def load_image(
    filename: str,
    size: tuple[int, int],
    subfolder: str = "assets",
) -> Optional[ctk.CTkImage]:
    """
    Load a PNG at a logical (width, height), retaining its source resolution.
    Returns None silently if the file is missing or Pillow is not installed.
    """
    try:
        img = _read_image(filename, subfolder)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except (ImportError, OSError, ValueError):
        return None


def load_image_fit_width(
    filename: str,
    width: int,
    subfolder: str = "assets",
) -> Optional[ctk.CTkImage]:
    """
    Load a PNG scaled to a target width, preserving the original aspect ratio.
    Use this for logos so they are never stretched or squashed.
    Returns None silently if the file is missing or Pillow is not installed.
    """
    try:
        img = _read_image(filename, subfolder)
        height = max(1, round(img.height * width / img.width))
        return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))
    except (ImportError, OSError, ValueError):
        return None


def set_taskbar_icon(window: ctk.CTk, filename: str = "PiNT_InAppLogo.png") -> None:
    """
    Set the window taskbar / title-bar icon from a PNG asset.

    Windows uses an ICO bitmap; other platforms use Tk's PNG icon support.
    Fails silently when the platform cannot set an icon or the asset is missing.
    """
    try:
        from PIL import Image
        src = asset_path(filename)
        if sys.platform != "win32":
            window.iconphoto(True, PhotoImage(master=window, file=str(src)))
            return
        dest = str(Path(tempfile.gettempdir()) / "pint_live_icon.ico")
        with Image.open(src) as image:
            image.save(dest, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])

        def apply_icon() -> None:
            try:
                window.iconbitmap(dest)
            except TclError:
                pass

        window.after(100, apply_icon)
    except Exception:
        pass
