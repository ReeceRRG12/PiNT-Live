"""
PiNT Live — DPI / display scale manager.

Detects the system display scale on Windows and applies it to
customtkinter so the UI looks crisp on high-DPI screens.
"""

import customtkinter as ctk

_scale: float = 1.0


def detect_scale() -> float:
    """
    Read the system DPI on Windows and return a scale factor.
    Returns 1.0 on non-Windows or if detection fails.

    Examples:
        96 dpi  → 1.0   (standard display)
        120 dpi → 1.25  (Windows 125 %)
        144 dpi → 1.5   (Windows 150 %)
        192 dpi → 2.0   (Windows 200 %)
    """
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        dc  = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX constant
        ctypes.windll.user32.ReleaseDC(0, dc)
        return round(dpi / 96.0, 2)
    except Exception:
        return 1.0


def apply_scale(scale: float) -> None:
    """
    Push the detected scale into customtkinter.
    Must be called before the CTk root window is created.
    """
    global _scale
    _scale = scale
    ctk.set_widget_scaling(scale)
    ctk.set_window_scaling(scale)


def current_scale() -> float:
    """Return the scale factor that was last applied."""
    return _scale
