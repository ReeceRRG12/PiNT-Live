"""
PiNT Live — sidebar widget.

The left-hand panel contains:
  • The PiNT Live logo
  • The switch IP list (each row has its own cog button for per-switch config)
  • A "Configure all switches…" button that opens the bulk config modal
  • The protocol toggle (SSH / Telnet)
  • The optional ARP-list block (Load ARP List(s)… / Clear / status)
  • The Poll Switches button
  • A progress bar + status label
  • Navigation buttons at the bottom

Per-switch vendor and credentials live on each _SwitchRow.  Shared
credentials live on the Sidebar.  The bulk modal and the per-row cog
popup both read/write that state directly so the two stay in sync.

The sidebar communicates outward through four callbacks set by the caller:
  on_poll_requested(config: dict)  — user clicked Poll; config holds form values
  on_navigate(key: str)            — user clicked a nav button ("poll" | "about")
  on_arp_load()                    — user clicked "Load ARP List(s)…"
  on_arp_clear()                   — user clicked "Clear" on the ARP block
"""

from __future__ import annotations

from tkinter import messagebox
import tkinter as tk

import customtkinter as ctk

from pint_live.ui import theme
from pint_live.ui import assets
from pint_live.vendors import REGISTRY as VENDORS


DEFAULT_VENDOR = "Ruckus"


# ── Switch-IP row ──────────────────────────────────────────────────────────

class _SwitchRow(ctk.CTkFrame):
    """
    A single row in the switch-IP list.

    Owns its own per-switch config:
      • vendor    — selected vendor name (defaults to Ruckus)
      • username  — per-switch override (empty string means "use shared")
      • password  — per-switch override (empty string means "use shared")
    """

    def __init__(
        self,
        master,
        on_remove: callable,
        on_configure: callable,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self.vendor:   str = DEFAULT_VENDOR
        self.username: str = ""
        self.password: str = ""

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="e.g. 192.168.1.1",
            width=150,
            font=theme.font_body(11),
        )
        self.entry.pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            self,
            text="⚙",     # gear glyph
            width=28, height=28,
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            font=theme.font_symbol(15),
            command=on_configure,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            self,
            text="−",     # minus sign
            width=28, height=28,
            fg_color=theme.REMOVE_BTN_BG,
            hover_color=theme.REMOVE_BTN_HOVER,
            font=theme.font_bold(12),
            command=on_remove,
        ).pack(side="left")

    @property
    def ip(self) -> str:
        return self.entry.get().strip()


# ── Per-switch config popup ────────────────────────────────────────────────

class _SwitchConfigPopup(ctk.CTkToplevel):
    """
    Small modal opened when the user clicks the cog next to one IP.
    Lets them pick a vendor and (if not using shared creds) enter
    per-switch credentials.  Changes are written back to the row on Save.
    """

    def __init__(self, master, row: _SwitchRow, use_shared_creds: bool):
        super().__init__(master)
        self._row = row

        ip_label = row.ip or "(no IP yet)"
        self.title(f"Configure {ip_label}")
        self.configure(fg_color=theme.SIDEBAR_BG)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        ctk.CTkLabel(
            body,
            text=f"Switch: {ip_label}",
            fg_color="transparent",
            text_color=theme.TEXT_PRIMARY,
            font=theme.font_bold(12),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        # Vendor
        ctk.CTkLabel(
            body,
            text="Vendor",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        self._vendor_var = tk.StringVar(value=row.vendor)
        ctk.CTkOptionMenu(
            body,
            values=list(VENDORS.keys()),
            variable=self._vendor_var,
            width=220,
            fg_color=theme.VENDOR_INACTIVE_BG,
            button_color=theme.VENDOR_ACTIVE_BG,
            button_hover_color=theme.VENDOR_HOVER,
            font=theme.font_body(11),
        ).pack(anchor="w", pady=(0, 10))

        # Credentials
        ctk.CTkLabel(
            body,
            text="Credentials",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        if use_shared_creds:
            ctk.CTkLabel(
                body,
                text=(
                    "Using shared credentials.\n"
                    "Open “Configure all switches…” and uncheck\n"
                    "“Use same credentials for all” to override per switch."
                ),
                fg_color="transparent",
                text_color=theme.TEXT_DIM,
                font=theme.font_body(10),
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(0, 10))
            self._username_entry = None
            self._password_entry = None
        else:
            ctk.CTkLabel(
                body,
                text="Username",
                fg_color="transparent",
                text_color=theme.TEXT_MUTED,
                font=theme.font_body(10),
                anchor="w",
            ).pack(fill="x")
            self._username_entry = ctk.CTkEntry(
                body, width=220, font=theme.font_body(11),
                placeholder_text="(falls back to shared if blank)",
            )
            self._username_entry.insert(0, row.username)
            self._username_entry.pack(anchor="w", pady=(0, 6))

            ctk.CTkLabel(
                body,
                text="Password",
                fg_color="transparent",
                text_color=theme.TEXT_MUTED,
                font=theme.font_body(10),
                anchor="w",
            ).pack(fill="x")
            self._password_entry = ctk.CTkEntry(
                body, width=220, show="●", font=theme.font_body(11),
                placeholder_text="(falls back to shared if blank)",
            )
            self._password_entry.insert(0, row.password)
            self._password_entry.pack(anchor="w", pady=(0, 10))

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")
        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=90, height=30,
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            font=theme.font_body(11),
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btn_row,
            text="Save",
            width=90, height=30,
            fg_color=theme.POLL_BTN_BG,
            hover_color=theme.POLL_BTN_HOVER,
            font=theme.font_bold(11),
            command=self._save_and_close,
        ).pack(side="right")

    def _save_and_close(self) -> None:
        self._row.vendor = self._vendor_var.get()
        if self._username_entry is not None:
            self._row.username = self._username_entry.get().strip()
        if self._password_entry is not None:
            self._row.password = self._password_entry.get()
        self.destroy()


# ── Bulk config modal ──────────────────────────────────────────────────────

class _BulkConfigDialog(ctk.CTkToplevel):
    """
    Modal opened by the "Configure all switches…" button.

    Shows the shared username/password fields at the top, then a table
    with one row per switch (IP | vendor | username | password).
    The "Use same credentials for all" checkbox toggles whether the
    per-switch cred fields are enabled.
    """

    def __init__(self, master, sidebar: "Sidebar"):
        super().__init__(master)
        self._sidebar = sidebar
        self._row_widgets: list[dict] = []

        self.title("Configure All Switches")
        self.configure(fg_color=theme.SIDEBAR_BG)
        self.resizable(True, True)
        self.minsize(620, 400)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self._build()
        self._apply_shared_state()

    def _build(self) -> None:
        body = ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        # ── Shared credentials block ────────────────────────────────────
        ctk.CTkLabel(
            body,
            text="Shared credentials",
            fg_color="transparent",
            text_color=theme.ACCENT,
            font=theme.font_bold(12),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        shared = ctk.CTkFrame(body, fg_color="transparent")
        shared.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            shared, text="Username", width=80, anchor="w",
            text_color=theme.TEXT_MUTED, font=theme.font_body(11),
        ).grid(row=0, column=0, sticky="w", pady=2)
        self._shared_user_entry = ctk.CTkEntry(
            shared, width=220, font=theme.font_body(11),
            placeholder_text="admin",
        )
        self._shared_user_entry.insert(0, self._sidebar.shared_username)
        self._shared_user_entry.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=2)

        ctk.CTkLabel(
            shared, text="Password", width=80, anchor="w",
            text_color=theme.TEXT_MUTED, font=theme.font_body(11),
        ).grid(row=1, column=0, sticky="w", pady=2)
        self._shared_pass_entry = ctk.CTkEntry(
            shared, width=220, show="●", font=theme.font_body(11),
        )
        self._shared_pass_entry.insert(0, self._sidebar.shared_password)
        self._shared_pass_entry.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=2)

        self._use_shared_var = tk.BooleanVar(value=self._sidebar.use_shared_creds)
        ctk.CTkCheckBox(
            body,
            text="Use same credentials for all switches",
            variable=self._use_shared_var,
            command=self._apply_shared_state,
            font=theme.font_body(11),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(6, 8))

        theme.separator(body, padx=0, pady=(2, 8))

        # ── Per-switch table ────────────────────────────────────────────
        ctk.CTkLabel(
            body,
            text="Per-switch configuration",
            fg_color="transparent",
            text_color=theme.ACCENT,
            font=theme.font_bold(12),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 2))
        for col, (text, width) in enumerate([
            ("IP / Host", 150),
            ("Vendor",    140),
            ("Username",  150),
            ("Password",  150),
        ]):
            ctk.CTkLabel(
                header, text=text, width=width, anchor="w",
                text_color=theme.TEXT_MUTED, font=theme.font_bold(10),
            ).grid(row=0, column=col, sticky="w", padx=(0, 6))

        table = ctk.CTkScrollableFrame(
            body, fg_color=theme.NAV_INACTIVE_BG, corner_radius=theme.CORNER_R,
        )
        table.pack(fill="both", expand=True, pady=(2, 8))

        for row in self._sidebar.switch_rows:
            self._add_table_row(table, row)

        # ── Footer buttons ──────────────────────────────────────────────
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(fill="x")
        ctk.CTkButton(
            footer,
            text="Cancel",
            width=90, height=30,
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            font=theme.font_body(11),
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            footer,
            text="Save",
            width=90, height=30,
            fg_color=theme.POLL_BTN_BG,
            hover_color=theme.POLL_BTN_HOVER,
            font=theme.font_bold(11),
            command=self._save_and_close,
        ).pack(side="right")

    def _add_table_row(self, parent, row: _SwitchRow) -> None:
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.pack(fill="x", pady=2)

        ip_text = row.ip or "(no IP yet)"
        ctk.CTkLabel(
            line, text=ip_text, width=150, anchor="w",
            text_color=theme.TEXT_PRIMARY, font=theme.font_body(11),
        ).grid(row=0, column=0, sticky="w", padx=(4, 6))

        vendor_var = tk.StringVar(value=row.vendor)
        vendor_menu = ctk.CTkOptionMenu(
            line,
            values=list(VENDORS.keys()),
            variable=vendor_var,
            width=140,
            fg_color=theme.VENDOR_INACTIVE_BG,
            button_color=theme.VENDOR_ACTIVE_BG,
            button_hover_color=theme.VENDOR_HOVER,
            font=theme.font_body(11),
        )
        vendor_menu.grid(row=0, column=1, sticky="w", padx=(0, 6))

        user_entry = ctk.CTkEntry(line, width=150, font=theme.font_body(11))
        user_entry.insert(0, row.username)
        user_entry.grid(row=0, column=2, sticky="w", padx=(0, 6))

        pass_entry = ctk.CTkEntry(
            line, width=150, show="●", font=theme.font_body(11),
        )
        pass_entry.insert(0, row.password)
        pass_entry.grid(row=0, column=3, sticky="w", padx=(0, 4))

        self._row_widgets.append({
            "row":         row,
            "vendor_var":  vendor_var,
            "user_entry":  user_entry,
            "pass_entry":  pass_entry,
        })

    def _apply_shared_state(self) -> None:
        """Enable or disable per-switch cred fields based on the checkbox."""
        state = "disabled" if self._use_shared_var.get() else "normal"
        for w in self._row_widgets:
            w["user_entry"].configure(state=state)
            w["pass_entry"].configure(state=state)

    def _save_and_close(self) -> None:
        self._sidebar.shared_username  = self._shared_user_entry.get().strip()
        self._sidebar.shared_password  = self._shared_pass_entry.get()
        self._sidebar.use_shared_creds = self._use_shared_var.get()

        for w in self._row_widgets:
            row = w["row"]
            row.vendor   = w["vendor_var"].get()
            row.username = w["user_entry"].get().strip()
            row.password = w["pass_entry"].get()

        self.destroy()


# ── Sidebar ────────────────────────────────────────────────────────────────

class Sidebar(ctk.CTkFrame):
    """
    Left sidebar.

    Instantiate, then set the callbacks before the mainloop starts:
        sidebar.on_poll_requested = my_poll_handler
        sidebar.on_navigate       = my_navigate_handler
        sidebar.on_arp_load       = my_arp_load_handler
        sidebar.on_arp_clear      = my_arp_clear_handler
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
        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        # Shared credential state (lives on the sidebar, edited via bulk modal)
        self.shared_username:  str  = ""
        self.shared_password:  str  = ""
        self.use_shared_creds: bool = True

        self._build()
        self._add_switch_row()   # start with one empty IP row

    # ── Public interface ───────────────────────────────────────────────────

    @property
    def switch_rows(self) -> list[_SwitchRow]:
        """Used by the bulk-config modal to enumerate switches."""
        return list(self._switch_rows)

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
            text="Switches",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(11),
            anchor="w",
        ).pack(fill="x", padx=14)

        ctk.CTkLabel(
            self,
            text="Click ⚙ to set vendor / per-switch credentials",
            fg_color="transparent",
            text_color=theme.TEXT_DIM,
            font=theme.font_body(9),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 2))

        # Container for the IP rows
        self._switches_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._switches_frame.pack(fill="x", padx=14, pady=(2, 0))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=14, pady=(4, 0))

        ctk.CTkButton(
            button_row,
            text="+ Add Switch",
            width=110, height=26,
            font=theme.font_body(11),
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            command=self._add_switch_row,
        ).pack(side="left")

        ctk.CTkButton(
            self,
            text="Configure all switches…",
            height=28,
            font=theme.font_bold(11),
            fg_color=theme.VENDOR_INACTIVE_BG,
            hover_color=theme.VENDOR_HOVER,
            command=self._open_bulk_config,
        ).pack(fill="x", padx=14, pady=(6, 0))

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
        # Use a holder list so the callbacks can reference `row` before
        # the variable is bound — avoids reconfiguring after creation.
        holder: list[_SwitchRow] = []
        row = _SwitchRow(
            self._switches_frame,
            on_remove=lambda: self._remove_switch_row(holder[0]),
            on_configure=lambda: self._open_row_config(holder[0]),
        )
        holder.append(row)
        row.pack(anchor="w", pady=2, fill="x")
        self._switch_rows.append(row)

    def _remove_switch_row(self, row: _SwitchRow) -> None:
        if len(self._switch_rows) <= 1:
            return   # always keep at least one row
        self._switch_rows.remove(row)
        row.destroy()

    # ── Modal launchers ────────────────────────────────────────────────────

    def _open_row_config(self, row: _SwitchRow) -> None:
        popup = _SwitchConfigPopup(self, row, self.use_shared_creds)
        popup.focus()

    def _open_bulk_config(self) -> None:
        dialog = _BulkConfigDialog(self, self)
        dialog.focus()

    # ── Protocol selection ─────────────────────────────────────────────────

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

    # ── Poll trigger ───────────────────────────────────────────────────────

    def _on_poll_click(self) -> None:
        rows_with_ip = [r for r in self._switch_rows if r.ip]
        if not rows_with_ip:
            messagebox.showwarning(
                "No Switches",
                "Please enter at least one switch IP or hostname.",
            )
            return

        # Duplicate IPs would double-poll and produce duplicate sheets
        # in the Excel export — flag it, but let the user override.
        seen: dict[str, int] = {}
        for r in rows_with_ip:
            key = r.ip.lower()
            seen[key] = seen.get(key, 0) + 1
        duplicates = sorted(ip for ip, count in seen.items() if count > 1)
        if duplicates:
            proceed = messagebox.askyesno(
                "Duplicate Switches",
                "The following IP/host appears more than once:\n\n"
                + "\n".join(f"• {ip}" for ip in duplicates)
                + "\n\nDuplicates will be polled multiple times and produce "
                "duplicate sheets in the export.\n\nContinue anyway?",
                icon="warning",
            )
            if not proceed:
                return

        # Resolve effective credentials per switch.
        switches = []
        missing_creds: list[str] = []
        for row in rows_with_ip:
            if self.use_shared_creds:
                user = self.shared_username
                pwd  = self.shared_password
            else:
                user = row.username or self.shared_username
                pwd  = row.password or self.shared_password

            if not user or not pwd:
                missing_creds.append(row.ip)

            switches.append({
                "host":     row.ip,
                "vendor":   row.vendor,
                "username": user,
                "password": pwd,
            })

        if missing_creds:
            messagebox.showwarning(
                "Missing Credentials",
                "No username/password set for:\n\n"
                + "\n".join(f"• {h}" for h in missing_creds)
                + "\n\nOpen “Configure all switches…” to fill them in.",
            )
            return

        config = {
            "protocol":         self._protocol.get(),
            "use_shared_creds": self.use_shared_creds,
            "shared_username":  self.shared_username,
            "shared_password":  self.shared_password,
            "switches":         switches,
        }
        self.on_poll_requested(config)
