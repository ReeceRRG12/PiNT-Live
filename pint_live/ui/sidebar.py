"""
PiNT Live — sidebar widget.

The left-hand panel contains:
  • A compact PiNT Live heading
  • The switch IP list (each row has an Edit button for per-switch config)
  • A "Credentials & vendors…" button that opens the bulk config modal
  • The protocol toggle (SSH / Telnet)
  • The optional ARP-list block (Load ARP List(s)… / Clear / status)
  • Persistent Poll Switches and Stop controls
  • A progress bar + status label
  • Navigation buttons at the bottom

Settings scroll independently, keeping run controls and status visible.

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
from pint_live.vendors import REGISTRY as VENDORS


DEFAULT_VENDOR = "Ruckus"


def _present_modal(dialog, parent, width: int, height: int, focus=None) -> None:
    """Size and centre a dialog using CTk's own DPI scaling on either platform."""
    dialog.geometry(f"{width}x{height}")
    dialog.transient(parent.winfo_toplevel())
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    dialog.bind("<Return>", lambda event: dialog._save_and_close())

    def present() -> None:
        if not dialog.winfo_exists():
            return
        dialog.update_idletasks()
        owner = parent.winfo_toplevel()
        x = max(0, owner.winfo_rootx() + (owner.winfo_width() - dialog.winfo_width()) // 2)
        y = max(0, owner.winfo_rooty() + (owner.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.lift()
        dialog.grab_set()
        (focus or dialog).focus_set()

    dialog.after(50, present)


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

        self.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(
            self, placeholder_text="IP address or hostname", width=150, height=34,
            font=theme.font_body(),
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            self, text="Edit", width=44, height=34,
            fg_color=theme.NAV_INACTIVE_BG, hover_color=theme.NAV_ACTIVE_BG,
            font=theme.font_body(14), command=on_configure,
        ).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(
            self, text="−", width=30, height=34,
            fg_color=theme.NAV_INACTIVE_BG, hover_color=theme.REMOVE_BTN_HOVER,
            text_color=theme.TEXT_MUTED, font=theme.font_bold(16), command=on_remove,
        ).grid(row=0, column=2)
        self._vendor_label = ctk.CTkLabel(
            self, text=self.vendor, height=20, anchor="w",
            text_color=theme.TEXT_MUTED, font=theme.font_body(13),
        )
        self._vendor_label.grid(row=1, column=0, sticky="w", padx=3)

    def refresh_vendor(self) -> None:
        self._vendor_label.configure(text=self.vendor)

    @property
    def ip(self) -> str:
        return self.entry.get().strip()


# ── Per-switch config popup ────────────────────────────────────────────────

class _SwitchConfigPopup(ctk.CTkToplevel):
    """
    Small modal opened when the user clicks Edit next to one IP.
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

        body = ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        ctk.CTkLabel(
            body,
            text=f"Switch: {ip_label}",
            fg_color="transparent",
            text_color=theme.TEXT_PRIMARY,
            font=theme.font_bold(14),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        # Vendor
        ctk.CTkLabel(
            body,
            text="Vendor",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(13),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        self._vendor_var = tk.StringVar(value=row.vendor)
        ctk.CTkOptionMenu(
            body,
            values=list(VENDORS.keys()),
            variable=self._vendor_var,
            width=280,
            fg_color=theme.VENDOR_INACTIVE_BG,
            button_color=theme.VENDOR_ACTIVE_BG,
            button_hover_color=theme.VENDOR_HOVER,
            font=theme.font_body(13),
        ).pack(anchor="w", pady=(0, 10))

        # Credentials
        ctk.CTkLabel(
            body,
            text="Credentials",
            fg_color="transparent",
            text_color=theme.TEXT_MUTED,
            font=theme.font_bold(13),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        if use_shared_creds:
            ctk.CTkLabel(
                body,
                text=(
                    "Using shared credentials.\n"
                    "Open “Credentials & vendors…” and uncheck\n"
                    "“Use same credentials for all” to override per switch."
                ),
                fg_color="transparent",
                text_color=theme.TEXT_DIM,
                font=theme.font_body(12),
                justify="left",
                anchor="w",
                wraplength=375,
            ).pack(fill="x", pady=(0, 10))
            self._username_entry = None
            self._password_entry = None
        else:
            ctk.CTkLabel(
                body,
                text="Username",
                fg_color="transparent",
                text_color=theme.TEXT_MUTED,
                font=theme.font_body(12),
                anchor="w",
            ).pack(fill="x")
            self._username_entry = ctk.CTkEntry(
                body, width=280, font=theme.font_body(13),
                placeholder_text="Use shared when blank",
            )
            self._username_entry.insert(0, row.username)
            self._username_entry.pack(anchor="w", pady=(0, 6))

            ctk.CTkLabel(
                body,
                text="Password",
                fg_color="transparent",
                text_color=theme.TEXT_MUTED,
                font=theme.font_body(12),
                anchor="w",
            ).pack(fill="x")
            self._password_entry = ctk.CTkEntry(
                body, width=280, show="●", font=theme.font_body(13),
                placeholder_text="Use shared when blank",
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
            font=theme.font_body(13),
            command=self.destroy,
        ).pack(side="left")
        ctk.CTkButton(
            btn_row,
            text="Save",
            width=90, height=30,
            fg_color=theme.POLL_BTN_BG,
            hover_color=theme.POLL_BTN_HOVER,
            font=theme.font_bold(13),
            command=self._save_and_close,
        ).pack(side="right")

        _present_modal(self, master, 430, 410, self._username_entry)

    def _save_and_close(self) -> None:
        self._row.vendor = self._vendor_var.get()
        self._row.refresh_vendor()
        if self._username_entry is not None:
            self._row.username = self._username_entry.get().strip()
        if self._password_entry is not None:
            self._row.password = self._password_entry.get()
        self.destroy()


# ── Bulk config modal ──────────────────────────────────────────────────────

class _BulkConfigDialog(ctk.CTkToplevel):
    """
    Modal opened by the "Credentials & vendors…" button.

    Shows the shared username/password fields at the top, then a table
    with one row per switch (IP | vendor | username | password).
    The "Use same credentials for all" checkbox toggles whether the
    per-switch cred fields are enabled.
    """

    def __init__(self, master, sidebar: "Sidebar"):
        super().__init__(master)
        self._sidebar = sidebar
        self._row_widgets: list[dict] = []

        self.title("Credentials & Vendors")
        self.configure(fg_color=theme.SIDEBAR_BG)
        self.resizable(True, True)
        self.minsize(730, 460)

        self._build()
        self._apply_shared_state()
        _present_modal(self, master, 780, 570, self._shared_user_entry)

    def _build(self) -> None:
        body = ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        # Reserve the actions before allocating the resizable switch table.
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(8, 0))

        # ── Shared credentials block ────────────────────────────────────
        ctk.CTkLabel(
            body,
            text="Shared credentials",
            fg_color="transparent",
            text_color=theme.ACCENT,
            font=theme.font_bold(14),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        shared = ctk.CTkFrame(body, fg_color="transparent")
        shared.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            shared, text="Username", width=80, anchor="w",
            text_color=theme.TEXT_MUTED, font=theme.font_body(13),
        ).grid(row=0, column=0, sticky="w", pady=2)
        self._shared_user_entry = ctk.CTkEntry(
            shared, width=280, font=theme.font_body(13),
            placeholder_text="admin",
        )
        self._shared_user_entry.insert(0, self._sidebar.shared_username)
        self._shared_user_entry.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=2)

        ctk.CTkLabel(
            shared, text="Password", width=80, anchor="w",
            text_color=theme.TEXT_MUTED, font=theme.font_body(13),
        ).grid(row=1, column=0, sticky="w", pady=2)
        self._shared_pass_entry = ctk.CTkEntry(
            shared, width=280, show="●", font=theme.font_body(13),
        )
        self._shared_pass_entry.insert(0, self._sidebar.shared_password)
        self._shared_pass_entry.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=2)

        self._use_shared_var = tk.BooleanVar(value=self._sidebar.use_shared_creds)
        ctk.CTkCheckBox(
            body,
            text="Use same credentials for all switches",
            variable=self._use_shared_var,
            command=self._apply_shared_state,
            font=theme.font_body(13),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(6, 8))

        theme.separator(body, padx=0, pady=(2, 8))

        # ── Per-switch table ────────────────────────────────────────────
        ctk.CTkLabel(
            body,
            text="Per-switch configuration",
            fg_color="transparent",
            text_color=theme.ACCENT,
            font=theme.font_bold(14),
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
                text_color=theme.TEXT_MUTED, font=theme.font_bold(12),
            ).grid(row=0, column=col, sticky="w", padx=(0, 6))

        table = ctk.CTkScrollableFrame(
            body, fg_color=theme.NAV_INACTIVE_BG, corner_radius=theme.CORNER_R,
        )
        table.pack(fill="both", expand=True, pady=(2, 8))

        for row in self._sidebar.switch_rows:
            self._add_table_row(table, row)

        # ── Footer buttons ──────────────────────────────────────────────
        ctk.CTkButton(
            footer,
            text="Cancel",
            width=90, height=30,
            fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG,
            font=theme.font_body(13),
            command=self.destroy,
        ).pack(side="left")
        ctk.CTkButton(
            footer,
            text="Save",
            width=90, height=30,
            fg_color=theme.POLL_BTN_BG,
            hover_color=theme.POLL_BTN_HOVER,
            font=theme.font_bold(13),
            command=self._save_and_close,
        ).pack(side="right")

    def _add_table_row(self, parent, row: _SwitchRow) -> None:
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.pack(fill="x", pady=2)

        ip_text = row.ip or "(no IP yet)"
        ctk.CTkLabel(
            line, text=ip_text, width=150, anchor="w",
            text_color=theme.TEXT_PRIMARY, font=theme.font_body(13),
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
            font=theme.font_body(13),
        )
        vendor_menu.grid(row=0, column=1, sticky="w", padx=(0, 6))

        user_entry = ctk.CTkEntry(line, width=150, font=theme.font_body(13))
        user_entry.insert(0, row.username)
        user_entry.grid(row=0, column=2, sticky="w", padx=(0, 6))

        pass_entry = ctk.CTkEntry(
            line, width=150, show="●", font=theme.font_body(13),
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
            row.refresh_vendor()
            row.username = w["user_entry"].get().strip()
            row.password = w["pass_entry"].get()

        self._sidebar._refresh_credentials_status()
        self.destroy()


# ── Sidebar ────────────────────────────────────────────────────────────────

class Sidebar(ctk.CTkFrame):
    """Scrollable setup with persistent run controls, progress and navigation."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.SIDEBAR_BG)
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("width", theme.SIDEBAR_W)
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_propagate(False)

        self.on_poll_requested: callable = lambda cfg: None
        self.on_navigate: callable = lambda key: None
        self.on_arp_load: callable = lambda: None
        self.on_arp_clear: callable = lambda: None
        self.on_stop_requested: callable = lambda: None
        self._switch_rows: list[_SwitchRow] = []
        self._protocol = tk.StringVar(value="SSH")
        self._include_raw_outputs = tk.BooleanVar(value=False)
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self.shared_username: str = ""
        self.shared_password: str = ""
        self.use_shared_creds: bool = True
        self._build()
        self._add_switch_row()

    @property
    def switch_rows(self) -> list[_SwitchRow]:
        return list(self._switch_rows)

    @property
    def include_raw_outputs(self) -> bool:
        return self._include_raw_outputs.get()

    def set_busy(self, busy: bool) -> None:
        self._poll_btn.configure(
            state="disabled" if busy else "normal",
            text="Polling…" if busy else "Poll switches",
        )
        self._stop_btn.configure(state="normal" if busy else "disabled", text="Stop")

    def set_stop_requested(self) -> None:
        self._stop_btn.configure(state="disabled", text="Stopping…")

    def set_status(self, text: str, colour: str = theme.TEXT_MUTED) -> None:
        self._status_label.configure(text=text, text_color=colour)

    def set_progress(self, value: float) -> None:
        self._progress_bar.set(value)

    def set_arp_status(self, text: str, *, loaded: bool) -> None:
        self._arp_label.configure(text=text, text_color=theme.LINK_UP if loaded else theme.TEXT_MUTED)
        if loaded:
            self._arp_clear_btn.pack(side="left", padx=(6, 0))
        else:
            self._arp_clear_btn.pack_forget()

    def set_nav_active(self, key: str) -> None:
        for k, btn in self._nav_buttons.items():
            btn.configure(
                text_color=theme.ACCENT if k == key else theme.TEXT_MUTED,
                fg_color=theme.NAV_ACTIVE_BG if k == key else theme.NAV_INACTIVE_BG,
            )

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 16))
        ctk.CTkLabel(
            header, text="PiNT Live", anchor="w", font=theme.font_heading(26),
            text_color=theme.TEXT_PRIMARY,
        ).pack(fill="x")
        ctk.CTkLabel(
            header, text="NETWORK DOCUMENTATION", anchor="w",
            font=theme.font_bold(10), text_color=theme.ACCENT,
        ).pack(fill="x", pady=(0, 2))

        self._settings = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme.SEPARATOR,
            scrollbar_button_hover_color=theme.ACCENT_HOVER,
        )
        self._settings.grid(row=1, column=0, sticky="nsew", padx=(8, 4))
        self._add_switch_ip_section()
        self._add_credentials_section()
        self._add_protocol_section()
        self._add_arp_section()
        self._add_export_options_section()

        self._controls = ctk.CTkFrame(self, fg_color=theme.SIDEBAR_BG, corner_radius=0)
        self._controls.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 14))
        theme.separator(self._controls, padx=0, pady=(0, 12))
        self._add_poll_button()
        self._add_status_area()
        self._add_nav_buttons()

    def _section(self, title: str, *, first: bool = False) -> None:
        ctk.CTkLabel(
            self._settings, text=title, anchor="w", font=theme.font_bold(13),
            text_color=theme.TEXT_PRIMARY,
        ).pack(fill="x", padx=8, pady=(0 if first else 18, 6))

    def _hint(self, text: str):
        label = ctk.CTkLabel(
            self._settings, text=text, anchor="w", justify="left",
            wraplength=theme.SIDEBAR_W - 52, font=theme.font_body(12),
            text_color=theme.TEXT_MUTED,
        )
        label.pack(fill="x", padx=8, pady=(2, 3))
        return label

    def _add_switch_ip_section(self) -> None:
        self._section("1   Add your switches", first=True)
        self._switches_frame = ctk.CTkFrame(self._settings, fg_color="transparent")
        self._switches_frame.pack(fill="x", padx=8)
        ctk.CTkButton(
            self._settings, text="+ Add switch", height=32,
            font=theme.font_body(), fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG, command=self._add_switch_row,
        ).pack(fill="x", padx=8, pady=(6, 0))

    def _add_credentials_section(self) -> None:
        self._section("2   Set credentials & vendors")
        ctk.CTkButton(
            self._settings, text="Credentials & vendors…", height=36,
            font=theme.font_bold(13), fg_color=theme.VENDOR_INACTIVE_BG,
            hover_color=theme.VENDOR_HOVER, command=self._open_bulk_config,
        ).pack(fill="x", padx=8)
        self._credentials_label = self._hint("Add a username and password to connect.")

    def _refresh_credentials_status(self) -> None:
        if self.use_shared_creds:
            configured = bool(self.shared_username and self.shared_password)
            text = "Shared credentials ready." if configured else "Add a username and password to connect."
        else:
            active_rows = [row for row in self._switch_rows if row.ip]
            configured = bool(active_rows) and all(
                (row.username or self.shared_username) and (row.password or self.shared_password)
                for row in active_rows
            )
            text = "Per-switch credentials ready." if configured else "Some switches still need credentials."
        self._credentials_label.configure(
            text=text, text_color=theme.LINK_UP if configured else theme.TEXT_MUTED,
        )

    def _add_protocol_section(self) -> None:
        self._section("3   Choose a connection")
        row = ctk.CTkFrame(self._settings, fg_color="transparent")
        row.pack(fill="x", padx=8)
        self._ssh_btn = ctk.CTkButton(
            row, text="SSH", width=115, height=32, font=theme.font_bold(13),
            fg_color=theme.PROTO_ACTIVE_SSH, command=lambda: self._select_protocol("SSH"),
        )
        self._ssh_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._telnet_btn = ctk.CTkButton(
            row, text="Telnet", width=115, height=32, font=theme.font_bold(13),
            fg_color=theme.PROTO_INACTIVE, hover_color=theme.NAV_ACTIVE_BG,
            command=lambda: self._select_protocol("Telnet"),
        )
        self._telnet_btn.pack(side="left", fill="x", expand=True)
        self._hint("SSH is recommended. Telnet is unencrypted.")

    def _add_arp_section(self) -> None:
        self._section("Enrich your results  ·  optional")
        self._hint("Match MAC addresses to IPs and hostnames with an ARP workbook.")
        row = ctk.CTkFrame(self._settings, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkButton(
            row, text="Load ARP lists…", width=165, height=32,
            font=theme.font_body(), fg_color=theme.NAV_INACTIVE_BG,
            hover_color=theme.NAV_ACTIVE_BG, command=lambda: self.on_arp_load(),
        ).pack(side="left")
        self._arp_clear_btn = ctk.CTkButton(
            row, text="Clear", width=58, height=32, font=theme.font_body(12),
            fg_color=theme.NAV_INACTIVE_BG, hover_color=theme.REMOVE_BTN_HOVER,
            command=lambda: self.on_arp_clear(),
        )
        self._arp_label = self._hint("No ARP lists loaded.")

    def _add_export_options_section(self) -> None:
        self._section("Excel export")
        self._raw_output_checkbox = ctk.CTkCheckBox(
            self._settings, text="Include raw CLI output", variable=self._include_raw_outputs,
            onvalue=True, offvalue=False, font=theme.font_body(12),
            text_color=theme.TEXT_MUTED, fg_color=theme.EXPORT_BTN_BG,
            hover_color=theme.EXPORT_BTN_HOVER, command=self._confirm_raw_outputs,
        )
        self._raw_output_checkbox.pack(fill="x", padx=8, pady=(2, 12))

    def _confirm_raw_outputs(self) -> None:
        if self._include_raw_outputs.get() and not messagebox.askyesno(
            "Sensitive Raw Output",
            "Raw output includes the complete running configuration and may contain "
            "password hashes, SNMP communities, usernames, IP addresses, and other "
            "sensitive client data.\n\nInclude it in Excel exports?",
            icon="warning", parent=self.winfo_toplevel(),
        ):
            self._include_raw_outputs.set(False)

    def _add_poll_button(self) -> None:
        row = ctk.CTkFrame(self._controls, fg_color="transparent")
        row.pack(fill="x")
        self._poll_btn = ctk.CTkButton(
            row, text="Poll switches", width=160, height=40, font=theme.font_bold(14),
            fg_color=theme.POLL_BTN_BG, hover_color=theme.POLL_BTN_HOVER,
            corner_radius=theme.CORNER_R, command=self._on_poll_click,
        )
        self._poll_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._stop_btn = ctk.CTkButton(
            row, text="Stop", width=76, height=40, font=theme.font_bold(12),
            fg_color=theme.REMOVE_BTN_BG, hover_color=theme.REMOVE_BTN_HOVER,
            corner_radius=theme.CORNER_R, state="disabled",
            command=lambda: self.on_stop_requested(),
        )
        self._stop_btn.pack(side="left")

    def _add_status_area(self) -> None:
        self._progress_bar = ctk.CTkProgressBar(
            self._controls, height=5, fg_color=theme.NAV_INACTIVE_BG,
            progress_color=theme.ACCENT,
        )
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", pady=(12, 5))
        self._status_label = ctk.CTkLabel(
            self._controls, text="Ready to connect", text_color=theme.TEXT_MUTED,
            font=theme.font_body(12), anchor="w", justify="left",
            wraplength=theme.SIDEBAR_W - 32,
        )
        self._status_label.pack(fill="x", pady=(0, 10))

    def _add_nav_buttons(self) -> None:
        row = ctk.CTkFrame(self._controls, fg_color="transparent")
        row.pack(fill="x")
        for key, label in [("poll", "Workspace"), ("about", "About")]:
            btn = ctk.CTkButton(
                row, text=label, width=90, height=30, font=theme.font_body(12),
                fg_color=theme.NAV_INACTIVE_BG, text_color=theme.TEXT_MUTED,
                hover_color=theme.NAV_ACTIVE_BG, corner_radius=theme.CORNER_R,
                command=lambda k=key: self.on_navigate(k),
            )
            btn.pack(side="left", fill="x", expand=True, padx=(0 if key == "poll" else 6, 0))
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
        row.entry.bind("<KeyRelease>", lambda event: self._refresh_credentials_status(), add="+")
        row.entry.focus_set()
        self._refresh_credentials_status()

    def _remove_switch_row(self, row: _SwitchRow) -> None:
        if len(self._switch_rows) <= 1:
            return   # always keep at least one row
        self._switch_rows.remove(row)
        row.destroy()
        self._refresh_credentials_status()

    # ── Modal launchers ────────────────────────────────────────────────────

    def _open_row_config(self, row: _SwitchRow) -> None:
        popup = _SwitchConfigPopup(self, row, self.use_shared_creds)
        popup.bind("<Destroy>", lambda event: self._refresh_credentials_status() if event.widget is popup else None, add="+")

    def _open_bulk_config(self) -> None:
        _BulkConfigDialog(self, self)

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
                parent=self.winfo_toplevel(),
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
                parent=self.winfo_toplevel(),
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
                parent=self.winfo_toplevel(),
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
                + "\n\nOpen “Credentials & vendors…” to fill them in.",
                parent=self.winfo_toplevel(),
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
