"""Choose a usable initial size while leaving native DPI handling to CTk.

CustomTkinter automatically scales windows and widgets on Windows and macOS.
Passing the system DPI to its custom scaling setters would apply it twice.
All application window dimensions should therefore use logical pixels.
"""

import customtkinter as ctk


def initial_window_size(
    window: ctk.CTk,
    preferred: tuple[int, int] = (1240, 820),
    margin: tuple[int, int] = (64, 96),
) -> tuple[int, int]:
    """Fit the initial logical size to the screen, leaving room for OS chrome.

    Tk reports physical pixels on DPI-aware Windows. Use the same conversion
    as CTk's geometry implementation; on macOS Tk already uses logical pixels
    and CTk's factor is one. This does not change the native scaling settings.
    Call after constructing the CTk root, before setting its geometry.
    """
    screen = (
        window._reverse_window_scaling(window.winfo_screenwidth()),
        window._reverse_window_scaling(window.winfo_screenheight()),
    )
    return tuple(
        max(1, min(target, available - inset))
        for target, available, inset in zip(preferred, screen, margin)
    )
