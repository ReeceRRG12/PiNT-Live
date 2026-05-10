"""
PiNT Live — asset loading helpers.

Handles image loading from the `assets/` folder and sets the
taskbar icon, with full support for PyInstaller frozen builds.
"""

import os
import sys
import tempfile
from typing import Optional

import customtkinter as ctk


def base_path() -> str:
    """
    Return the directory containing bundled assets.

    - When frozen by PyInstaller, files are extracted to sys._MEIPASS.
    - When running from source, assets live next to this file (pint_live/ui/).
    """
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def load_image(
    filename: str,
    size: tuple[int, int],
    subfolder: str = "assets",
) -> Optional[ctk.CTkImage]:
    """
    Load a PNG at an exact (width, height) size.
    Returns None silently if the file is missing or Pillow is not installed.
    """
    try:
        from PIL import Image
        path = os.path.join(base_path(), subfolder, filename)
        img  = Image.open(path).convert("RGBA").resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
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
        from PIL import Image
        path   = os.path.join(base_path(), subfolder, filename)
        img    = Image.open(path).convert("RGBA")
        height = int(img.height * (width / img.width))
        img    = img.resize((width, height), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))
    except Exception:
        return None


def set_taskbar_icon(window: ctk.CTk, filename: str = "PiNT_InAppLogo.png") -> None:
    """
    Set the window taskbar / title-bar icon from a PNG asset.

    CTk on Windows requires an .ico file for iconbitmap(), so we convert
    the PNG to a temporary ICO at runtime. Fails silently if Pillow is
    missing or the file doesn't exist.
    """
    try:
        from PIL import Image
        src  = os.path.join(base_path(), "assets", filename)
        dest = os.path.join(tempfile.gettempdir(), "pint_live_icon.ico")
        Image.open(src).save(dest, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
        window.after(100, lambda: window.iconbitmap(dest))
    except Exception:
        pass
