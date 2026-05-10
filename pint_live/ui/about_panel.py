"""
PiNT Live — About panel.

Shown when the user clicks the About nav button in the sidebar.
"""

import webbrowser
import customtkinter as ctk

from pint_live.ui import theme
from pint_live.ui import assets


class AboutPanel(ctk.CTkFrame):
    """
    Centred about screen showing the logo, version, description,
    and contact / repository links.
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.BG)
        super().__init__(master, **kwargs)
        self._build()

    def _build(self) -> None:
        # Centre everything in the frame
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.46, anchor="center")

        self._add_logo(container)
        self._add_title(container)
        self._add_version(container)
        theme.separator(container, padx=20, pady=14)
        self._add_description(container)
        theme.separator(container, padx=20, pady=14)
        self._add_credits(container)
        self._add_footer(container)

    def _add_logo(self, parent) -> None:
        logo = assets.load_image_fit_width("PiNT_InAppLogo.png", width=260)
        if logo:
            ctk.CTkLabel(
                parent, image=logo, text="", fg_color="transparent"
            ).pack(pady=(0, 10))
        else:
            # Fallback text if the image file hasn't been added yet
            ctk.CTkLabel(
                parent,
                text="PiNT Live",
                fg_color="transparent",
                text_color=theme.ACCENT,
                font=theme.font_heading(22),
            ).pack(pady=(0, 10))

    def _add_title(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="PiNT Live — Pi Network Tools, Live",
            fg_color="transparent",
            text_color=theme.ACCENT,
            font=theme.font_heading(16),
        ).pack()

    def _add_version(self, parent) -> None:
        from pint_live import __version__
        ctk.CTkLabel(
            parent,
            text=f"Version {__version__}",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_body(12),
        ).pack(pady=(3, 0))

    def _add_description(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text=(
                "Automated network documentation for Ruckus, Cisco IOS, and HP/Aruba switches.\n"
                "SSH into your devices, pull live data, and export clean Excel workbooks\n"
                "with VLAN assignments, MAC addresses, and port states."
            ),
            fg_color="transparent",
            text_color=theme.TEXT_PRIMARY,
            font=theme.font_body(13),
            justify="center",
        ).pack()

    def _add_credits(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="Built by Reece Rainer",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_body(12),
        ).pack()

        links = [
            ("reece@pinetworktools.com",       "mailto:reece@pinetworktools.com"),
            ("github.com/ReeceRRG12/PiNT-Live","https://github.com/ReeceRRG12/PiNT-Live"),
        ]
        for text, url in links:
            lbl = ctk.CTkLabel(
                parent,
                text=text,
                fg_color="transparent",
                text_color=theme.ACCENT,
                font=theme.font_link(12),
                cursor="hand2",
            )
            lbl.pack(pady=3)
            lbl.bind("<Button-1>", lambda _, u=url: webbrowser.open(u))

    def _add_footer(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="Fully Open Source — Built with ❤️ for the networking community",
            fg_color="transparent",
            text_color=theme.TEXT_DIM,
            font=theme.font_body(11),
        ).pack(pady=(14, 0))
