"""
PiNT Live — sidebar widget.

The left-hand panel contains:
  • The PiNT Live logo
  • The configuration form  (switch IPs, protocol, vendor, credentials)
  • The Poll Switches button
  • A progress bar + status label
  • Navigation buttons at the bottom  (Poll Switches view / About)

The sidebar communicates outward through two callbacks set by the caller:
  on_poll_requested(config: dict)  — user clicked Poll; config holds form values
  on_navigate(key: str)            — user clicked a nav button ("poll" | "about")
"""

from __future__ import annotations

from tkinter import messagebox
import tkinter as tk

import customtkinter as ctk

from pint_live.ui import theme
from pint_live.ui import assets
from pint_live.vendors import REGISTRY as VENDORS


# ── Switch-IP row ──────────────────────────────────────────────────────────

class _SwitchRow(ctk.CTkFrame):
    """
    A single row in the switch-IP list.
    Contains an entry field and a remove button.
    """

    def __init__(self, master, on_remove: callable, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="e.g. 192.168.1.1",
            width=180,
            font=theme.font_body(11),
        )
        self.entry.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self,
            text="−",
            width=28, height=28,
            fg_color=theme.REMOVE_BTN_BG,
            hover_color=theme.REMOVE_BTN_HOVER,
            font=theme.font_bold(12),
            command=on_remove,
        ).pack(side="left")

    @property
    def value(self) -> str:
        return self.entry.get().strip()


# ── Sidebar ────────────────────────────────────────────────────────────────

class Sidebar(ctk.CTkFrame):
    """
    Left sidebar.

    Instantiate, then set the two callbacks before the mainloop starts:
        sidebar.on_poll_requested = my_poll_handler
        sidebar.on_navigate       = my_navigate_handler
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.SIDEBAR_BG)
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("width", theme.SIDEBAR_W)
        super().__init__(master, **kwargs)
        self.pack_propagate(False)

        # Callbacks — assign these after construction
        self.on_poll_requested: callable = lambda cfg: None
        self.on_navigate:       callable = lambda key: None
        self.on_arp_load:       callable = lambda: None
        self.on_arp_clear:      callable = lambda: None

        # Internal state
        self._switch_rows: list[_SwitchRow] = []
        self._protocol  = tk.StringVar(value="SSH")
        self._vendor    = tk.StringVar(value="Ruckus")
        self._use_shared_creds = tk.BooleanVar(value=True)
        self._nav_buttons:    dict[str, ctk.CTkButton] = {}
        self._vendor_buttons: dict[str, ctk.CTkButton] = {}

        self._build()
        self._add_switch_row()   # start with one empty IP row

    # ── Public interface ───────────────────────────────────────────────────

    def set_busy(self, busy: bool) -> None:
        """Disable or re-enable the Poll button during a poll run."""
        self._poll_btn.configure(
            state="disabled" if busy else "normal",
            text="Polling…" if busy else "Poll Switches",
        )

    def set_status(self, text: str, colour: str = theme.TEXT_MUTED) -> None:
        """Update the status label below the progress bar."""
        self._status_label.configure(text=text, text_color=colour)

    def set_progress(self, value: float) -> None:
        """Set the progress bar (0.0 – 1.0)."""
        self._progress_bar.set(value)

    def set_arp_status(self, text: str, *, loaded: bool) -> None:
        """Update the ARP-list status line and show/hide the clear button."""
        colour = theme.LINK_UP if loaded else theme.TEXT_MUTED
        self._arp_label.configure(text=text, text_color=colour)
        if loaded:
            self._arp_clear_btn.pack(side="left", padx=(6, 0))
        else:
            self._arp_clear_btn.pack_forget()

    def set_nav_active(self, key: str) -> None:
        """Highlight the active navigation button."""
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(text_color=theme.ACCENT, fg_color=theme.NAV_ACTIVE_BG)
            else:
                btn.configure(text_color=theme.TEXT_MUTED, fg_color=theme.NAV_INACTIVE_BG)

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        tk.Frame(self, bg=theme.SIDEBAR_BG, height=8).pack(fill="x")

        self._add_logo()
        theme.separator(self, pady=(4, 8))
        self._add_switch_ip_section()
        theme.separator(self, pady=(6, 6))
        self._add_protocol_section()
        theme.separator(self, pady=(6, 6))
        self._add_vendor_section()
        theme.separator(self, pady=(6, 6))
        self._add_credentials_section()
        theme.separator(self, pady=(6, 6))
        self._add_arp_section()
        self._add_poll_button()
        self._add_status_area()

        # Spacer pushes nav buttons to the bottom
        ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG, corner_radius=0).pack(
            fill="both", expand=True
        )
        theme.separator(self, pady=(6, 4))
        self._add_nav_buttons()
        theme.separator(self, pady=(4, 2))
        tk.Frame(self, bg=theme.SIDEBAR_BG, height=8).pack(fill="x")

    def _add_logo(self) -> None:
        logo = assets.load_image_fit_width(
            "PiNT_InAppLogo.png",
            width=theme.SIDEBAR_W - 24,
        )
        if logo:
            ctk.CTkLabel(
                self, image=logo, text="", fg_color="transparent"
            ).pack(padx=12, pady=(0, 6))
        else:
            ctk.CTkLabel(
                self,
                text="PiNT Live",
                fg_color="transparent",
                text_color=theme.ACCENT,
                font=theme.font_heading(16),
            ).pack(pady=(6, 6))

    def _add_switch_ip_section(self) -> None:
        ctk.CTkLabel(
            self,
            text="Switch IPs",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", padx=14)

        # Scrollable container for the IP rows
        self._switches_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._switches_frame.pack(fill="x", padx=14, pady=(4, 0))

        ctk.CTkButton(
            self,
            text="+ Add Switch",
            width=110, height=26,
            font=theme.font_body(11),
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            command=self._add_switch_row,
        ).pack(anchor="w", padx=14, pady=(4, 0))

    def _add_protocol_section(self) -> None:
        ctk.CTkLabel(
            self,
            text="Protocol",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", padx=14)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(4, 0))

        self._ssh_btn = ctk.CTkButton(
            row,
            text="SSH",
            width=74, height=28,
            font=theme.font_bold(11),
            fg_color=theme.PROTO_ACTIVE_SSH,
            command=lambda: self._select_protocol("SSH"),
        )
        self._ssh_btn.pack(side="left", padx=(0, 6))

        self._telnet_btn = ctk.CTkButton(
            row,
            text="Telnet",
            width=74, height=28,
            font=theme.font_bold(11),
            fg_color=theme.PROTO_INACTIVE,
            hover_color="#6c757d",
            command=lambda: self._select_protocol("Telnet"),
        )
        self._telnet_btn.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            row,
            text="⚠ Unencrypted",
            fg_color="transparent",
            text_color=theme.WARNING,
            font=theme.font_body(10),
        ).pack(side="left")

    def _add_vendor_section(self) -> None:
        ctk.CTkLabel(
            self,
            text="Vendor",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", padx=14)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(4, 0))

        for name in VENDORS:
            btn = ctk.CTkButton(
                row,
                text=name,
                width=80, height=28,
                font=theme.font_body(11),
                fg_color=theme.VENDOR_INACTIVE_BG,
                hover_color=theme.VENDOR_HOVER,
                command=lambda n=name: self._select_vendor(n),
            )
            btn.pack(side="left", padx=(0, 5))
            self._vendor_buttons[name] = btn

        self._select_vendor("Ruckus")

    def _add_credentials_section(self) -> None:
        creds_frame = ctk.CTkFrame(self, fg_color="transparent")
        creds_frame.pack(fill="x", padx=14)

        # Username
        ctk.CTkLabel(
            creds_frame,
            text="Username",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        self._username_entry = ctk.CTkEntry(
            creds_frame,
            placeholder_text="admin",
            width=220,
            font=theme.font_body(11),
        )
        self._username_entry.pack(anchor="w", pady=(0, 6))

        # Password
        ctk.CTkLabel(
            creds_frame,
            text="Password",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        self._password_entry = ctk.CTkEntry(
            creds_frame,
            show="●",
            width=220,
            font=theme.font_body(11),
        )
        self._password_entry.pack(anchor="w", pady=(0, 6))

        ctk.CTkCheckBox(
            creds_frame,
            text="Use for all switches",
            variable=self._use_shared_creds,
            font=theme.font_body(11),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w")

    def _add_arp_section(self) -> None:
        ctk.CTkLabel(
            self,
            text="ARP Lists (optional)",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", padx=14)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(4, 0))

        ctk.CTkButton(
            row,
            text="Load ARP List(s)…",
            width=140, height=26,
            font=theme.font_body(11),
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            command=lambda: self.on_arp_load(),
        ).pack(side="left")

        self._arp_clear_btn = ctk.CTkButton(
            row,
            text="Clear",
            width=60, height=26,
            font=theme.font_body(11),
            fg_color=theme.REMOVE_BTN_BG,
            hover_color=theme.REMOVE_BTN_HOVER,
            command=lambda: self.on_arp_clear(),
        )
        # not packed until an ARP list is loaded

        self._arp_label = ctk.CTkLabel(
            self,
            text="No ARP lists loaded.",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_body(10),
            anchor="w",
            wraplength=theme.SIDEBAR_W - 28,
            justify="left",
        )
        self._arp_label.pack(fill="x", padx=14, pady=(4, 0))

    def _add_poll_button(self) -> None:
        self._poll_btn = ctk.CTkButton(
            self,
            text="Poll Switches",
            height=38,
            font=theme.font_bold(13),
            fg_color=theme.POLL_BTN_BG,
            hover_color=theme.POLL_BTN_HOVER,
            corner_radius=theme.CORNER_R,
            command=self._on_poll_click,
        )
        self._poll_btn.pack(fill="x", padx=14, pady=(10, 0))

    def _add_status_area(self) -> None:
        self._progress_bar = ctk.CTkProgressBar(self, height=6)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=14, pady=(8, 2))

        self._status_label = ctk.CTkLabel(
            self,
            text="Ready.",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_body(10),
            anchor="w",
            wraplength=theme.SIDEBAR_W - 28,
        )
        self._status_label.pack(fill="x", padx=14)

    def _add_nav_buttons(self) -> None:
        nav_items = [
            ("poll",  "Poll Switches"),
            ("about", "About"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self,
                text=f"  {label}",
                anchor="w",
                fg_color=theme.NAV_INACTIVE_BG,
                text_color=theme.TEXT_MUTED,
                hover_color=theme.NAV_ACTIVE_BG,
                font=theme.font_bold(11),
                height=38,
                corner_radius=theme.CORNER_R,
                border_width=0,
                cursor="hand2",
                command=lambda k=key: self.on_navigate(k),
            )
            btn.pack(fill="x", padx=6, pady=2)
            self._nav_buttons[key] = btn

    # ── Switch IP row management ───────────────────────────────────────────

    def _add_switch_row(self) -> None:
        # Use a holder list so the remove callback can reference `row`
        # before the variable is bound — avoids reconfiguring after creation.
        holder = []
        row = _SwitchRow(
            self._switches_frame,
            on_remove=lambda: self._remove_switch_row(holder[0]),
        )
        holder.append(row)
        row.pack(anchor="w", pady=2)
        self._switch_rows.append(row)

    def _remove_switch_row(self, row: _SwitchRow) -> None:
        if len(self._switch_rows) <= 1:
            return   # always keep at least one row
        self._switch_rows.remove(row)
        row.destroy()

    # ── Protocol / vendor selection ────────────────────────────────────────

    def _select_protocol(self, proto: str) -> None:
        if proto == "Telnet":
            confirmed = messagebox.askyesno(
                "Security Warning",
                "Are you sure you want to use Telnet?\n\n"
                "Telnet is not a secure connection method. Your credentials and all "
                "switch output will be transmitted in plaintext and could be intercepted.\n\n"
                "SSH is strongly recommended.",
                icon="warning",
            )
            if not confirmed:
                return

        self._protocol.set(proto)
        if proto == "SSH":
            self._ssh_btn.configure(fg_color=theme.PROTO_ACTIVE_SSH)
            self._telnet_btn.configure(fg_color=theme.PROTO_INACTIVE)
        else:
            self._ssh_btn.configure(fg_color=theme.PROTO_INACTIVE)
            self._telnet_btn.configure(fg_color=theme.PROTO_ACTIVE_TELNET)

    def _select_vendor(self, name: str) -> None:
        self._vendor.set(name)
        for vendor_name, btn in self._vendor_buttons.items():
            if vendor_name == name:
                btn.configure(fg_color=theme.VENDOR_ACTIVE_BG)
            else:
                btn.configure(fg_color=theme.VENDOR_INACTIVE_BG)

    # ── Poll trigger ───────────────────────────────────────────────────────

    def _on_poll_click(self) -> None:
        hosts = [r.value for r in self._switch_rows if r.value]
        if not hosts:
            messagebox.showwarning(
                "No Switches",
                "Please enter at least one switch IP or hostname.",
            )
            return

        username = self._username_entry.get().strip()
        password = self._password_entry.get()
        if not username or not password:
            messagebox.showwarning(
                "Missing Credentials",
                "Please enter a username and password.",
            )
            return

        config = {
            "hosts":            hosts,
            "protocol":         self._protocol.get(),
            "vendor":           self._vendor.get(),
            "username":         username,
            "password":         password,
            "use_shared_creds": self._use_shared_creds.get(),
        }
        self.on_poll_requested(config)
