"""
PiNT Live — visual theme constants.

All colours, font sizes, and layout measurements live here.
Change a value once and it updates everywhere in the UI.
"""

import customtkinter as ctk

# ── Background colours ─────────────────────────────────────────────────────
BG          = "#1a1a2e"   # main window background
SIDEBAR_BG  = "#16213e"   # left sidebar
PANEL_BG    = "#1e1e2e"   # slightly lifted panels (e.g. results area)

# ── Accent / interactive ───────────────────────────────────────────────────
ACCENT          = "#00d4ff"   # cyan — active nav, headings, links
ACCENT_HOVER    = "#0fa8c8"

# ── Separator lines ────────────────────────────────────────────────────────
SEPARATOR       = "#0f3460"

# ── Text ───────────────────────────────────────────────────────────────────
TEXT_PRIMARY    = "#eeeeee"
TEXT_MUTED      = "#888888"
TEXT_DIM        = "#555555"

# ── Navigation buttons ─────────────────────────────────────────────────────
NAV_ACTIVE_BG   = "#1a3050"
NAV_INACTIVE_BG = "#111d2e"

# ── Vendor selection buttons ───────────────────────────────────────────────
VENDOR_ACTIVE_BG   = "#457b9d"
VENDOR_INACTIVE_BG = "#1d3557"
VENDOR_HOVER       = "#457b9d"

# ── Protocol buttons ───────────────────────────────────────────────────────
PROTO_ACTIVE_SSH    = "#1F6AA5"   # default blue
PROTO_ACTIVE_TELNET = "#ae2012"   # red — danger
PROTO_INACTIVE      = "#495057"

# ── Link-state colours (results table rows) ────────────────────────────────
LINK_UP       = "#74c69d"   # green text
LINK_DOWN     = "#e63946"   # red text
LINK_DISABLED = "#adb5bd"   # grey text

# ── Action buttons ─────────────────────────────────────────────────────────
POLL_BTN_BG     = "#1F6AA5"
POLL_BTN_HOVER  = "#144870"
EXPORT_BTN_BG   = "#2d6a4f"
EXPORT_BTN_HOVER= "#40916c"
REMOVE_BTN_BG   = "#9b2226"
REMOVE_BTN_HOVER= "#ae2012"

# ── Warning text ───────────────────────────────────────────────────────────
WARNING = "#f4a261"

# ── Layout ─────────────────────────────────────────────────────────────────
SIDEBAR_W  = 270   # pixels (before DPI scaling)
CORNER_R   = 6


# ── Font helpers ───────────────────────────────────────────────────────────
# Call these wherever you need a font — they always return a fresh CTkFont.

def font_heading(size: int = 13) -> ctk.CTkFont:
    return ctk.CTkFont("Arial", size, weight="bold")

def font_body(size: int = 11) -> ctk.CTkFont:
    return ctk.CTkFont("Arial", size)

def font_bold(size: int = 11) -> ctk.CTkFont:
    return ctk.CTkFont("Arial", size, weight="bold")

def font_small(size: int = 10) -> ctk.CTkFont:
    return ctk.CTkFont("Arial", size)

def font_link(size: int = 12) -> ctk.CTkFont:
    return ctk.CTkFont("Arial", size, underline=True)

def font_symbol(size: int = 15) -> ctk.CTkFont:
    # Windows ships Segoe UI Symbol; renders glyphs like ⚙ properly,
    # unlike Arial which falls back to a thin outline.
    return ctk.CTkFont("Segoe UI Symbol", size)


# ── Separator helper ───────────────────────────────────────────────────────

def separator(parent, padx: int = 12, pady: tuple = (4, 4)) -> ctk.CTkFrame:
    """Return a thin horizontal separator line and pack it automatically."""
    sep = ctk.CTkFrame(parent, fg_color=SEPARATOR, height=2, corner_radius=0)
    sep.pack(fill="x", padx=padx, pady=pady)
    return sep
