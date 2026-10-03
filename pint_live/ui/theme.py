"""
PiNT Live — visual theme constants.

All colours, font sizes, and layout measurements live here.
Change a value once and it updates everywhere in the UI.
"""

import sys

import customtkinter as ctk

FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans"

# ── Background colours ─────────────────────────────────────────────────────
BG          = "#101722"   # main window background
SIDEBAR_BG  = "#151f2d"   # left sidebar
PANEL_BG    = "#192536"   # slightly lifted panels (e.g. results area)

# ── Accent / interactive ───────────────────────────────────────────────────
ACCENT          = "#5cd6c0"   # cyan — active nav, headings, links
ACCENT_HOVER    = "#40bba7"

# ── Separator lines ────────────────────────────────────────────────────────
SEPARATOR       = "#2b3a4e"

# ── Text ───────────────────────────────────────────────────────────────────
TEXT_PRIMARY    = "#edf3fa"
TEXT_MUTED      = "#a4b3c7"
TEXT_DIM        = "#8496ad"

# ── Navigation buttons ─────────────────────────────────────────────────────
NAV_ACTIVE_BG   = "#25443f"
NAV_INACTIVE_BG = "#202e40"

# ── Vendor selection buttons ───────────────────────────────────────────────
VENDOR_ACTIVE_BG   = "#365970"
VENDOR_INACTIVE_BG = "#253b50"
VENDOR_HOVER       = "#365970"

# ── Protocol buttons ───────────────────────────────────────────────────────
PROTO_ACTIVE_SSH    = "#187d70"   # default blue
PROTO_ACTIVE_TELNET = "#944344"   # red — danger
PROTO_INACTIVE      = "#29394d"

# ── Link-state colours (results table rows) ────────────────────────────────
LINK_UP       = "#79d9b1"   # green text
LINK_DOWN     = "#f49898"   # red text
LINK_DISABLED = "#9aa9bd"   # grey text

# ── Action buttons ─────────────────────────────────────────────────────────
POLL_BTN_BG     = "#187d70"
POLL_BTN_HOVER  = "#22695f"
EXPORT_BTN_BG   = "#187d70"
EXPORT_BTN_HOVER= "#22695f"
REMOVE_BTN_BG   = "#6c343e"
REMOVE_BTN_HOVER= "#944344"

# ── Warning text ───────────────────────────────────────────────────────────
WARNING = "#efc181"

# ── Layout ─────────────────────────────────────────────────────────────────
SIDEBAR_W  = 320   # pixels (before DPI scaling)
CORNER_R   = 10


# ── Font helpers ───────────────────────────────────────────────────────────
# Call these wherever you need a font — they always return a fresh CTkFont.

def font_heading(size: int = 15) -> ctk.CTkFont:
    return ctk.CTkFont(FONT_FAMILY, size, weight="bold")

def font_body(size: int = 13) -> ctk.CTkFont:
    return ctk.CTkFont(FONT_FAMILY, size)

def font_bold(size: int = 15) -> ctk.CTkFont:
    return ctk.CTkFont(FONT_FAMILY, size, weight="bold")

def font_small(size: int = 12) -> ctk.CTkFont:
    return ctk.CTkFont(FONT_FAMILY, size)

def font_link(size: int = 12) -> ctk.CTkFont:
    return ctk.CTkFont(FONT_FAMILY, size, underline=True)

def font_symbol(size: int = 15) -> ctk.CTkFont:
    # Windows ships Segoe UI Symbol; renders glyphs like ⚙ properly,
    # unlike Arial which falls back to a thin outline.
    return ctk.CTkFont("Segoe UI Symbol", size)


# ── Separator helper ───────────────────────────────────────────────────────

def separator(parent, padx: int = 12, pady: tuple = (4, 4)) -> ctk.CTkFrame:
    """Return a thin horizontal separator line and pack it automatically."""
    sep = ctk.CTkFrame(parent, fg_color=SEPARATOR, height=1, corner_radius=0)
    sep.pack(fill="x", padx=padx, pady=pady)
    return sep
