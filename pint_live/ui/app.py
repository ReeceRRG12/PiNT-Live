"""
PiNT Live — main application window.

This file is intentionally slim.  All visual logic lives in the
individual UI modules; this file only:
  • Creates the root window and lays out the top-level frames
  • Wires the sidebar callbacks to the polling logic
  • Runs the background thread and message queue
  • Handles the Excel export flow
"""

from __future__ import annotations

import queue
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from pint_live.core.session import Credentials, SwitchTarget, open_session, SessionError
from pint_live.exporters    import excel as excel_exporter
from pint_live.models       import ParsedSwitchData
from pint_live.vendors      import REGISTRY as VENDORS

from pint_live.ui            import theme
from pint_live.ui            import assets
from pint_live.ui.scale_manager import detect_scale, apply_scale
from pint_live.ui.sidebar       import Sidebar
from pint_live.ui.results_table import ResultsTable
from pint_live.ui.about_panel   import AboutPanel


class PintLiveApp(ctk.CTk):
    """
    Root window for PiNT Live.

    Layout
    ──────
    ┌─────────────┬───────────────────────────────┐
    │  Sidebar    │  Content area                 │
    │  (fixed)    │  (fills remaining space)      │
    │             │                               │
    │  Logo       │  ResultsTable  ← poll view    │
    │  Config     │  AboutPanel    ← about view   │
    │  form       │                               │
    │  Nav        │  [ Export to Excel ]          │
    └─────────────┴───────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        self.title("PiNT Live")
        _s = detect_scale()
        apply_scale(_s)
        self.geometry(f"{round(1200 * _s)}x{round(800 * _s)}")
        self.minsize(900, 600)
        self.resizable(True, True)
        self.configure(fg_color=theme.BG)

        # App state
        self._poll_results: list[ParsedSwitchData] = []
        self._msg_queue: queue.Queue = queue.Queue()

        self._build_layout()
        assets.set_taskbar_icon(self)

        # Start with the poll view active
        self._navigate("poll")

        # Begin draining the background thread's message queue
        self._drain_message_queue()

    # ── Layout construction ────────────────────────────────────────────────

    def _build_layout(self) -> None:
        # ── Sidebar (left, fixed width) ────────────────────────────────────
        self._sidebar = Sidebar(self)
        self._sidebar.pack(side="left", fill="y")

        # Wire sidebar callbacks
        self._sidebar.on_poll_requested = self._start_poll
        self._sidebar.on_navigate       = self._navigate

        # ── Content area (right, fills remaining space) ────────────────────
        self._content = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        # Results view = table + export button
        self._results_view = ctk.CTkFrame(self._content, fg_color=theme.BG, corner_radius=0)
        self._results_view.place(relwidth=1, relheight=1)

        self._results_table = ResultsTable(self._results_view)
        self._results_table.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        self._export_btn = ctk.CTkButton(
            self._results_view,
            text="Export to Excel",
            height=36,
            font=theme.font_bold(13),
            fg_color=theme.EXPORT_BTN_BG,
            hover_color=theme.EXPORT_BTN_HOVER,
            corner_radius=theme.CORNER_R,
            state="disabled",
            command=self._export,
        )
        self._export_btn.pack(fill="x", padx=12, pady=(0, 12))

        # About view
        self._about_view = AboutPanel(self._content)
        self._about_view.place(relwidth=1, relheight=1)

    # ── Navigation ─────────────────────────────────────────────────────────

    def _navigate(self, key: str) -> None:
        """Raise the correct content panel and update the sidebar nav highlight."""
        self._sidebar.set_nav_active(key)
        if key == "about":
            self._about_view.tkraise()
        else:
            self._results_view.tkraise()

    # ── Polling ────────────────────────────────────────────────────────────

    def _start_poll(self, config: dict) -> None:
        """
        Called by the sidebar when the user clicks Poll Switches.
        Validates the vendor selection, locks the UI, and fires the worker thread.
        """
        vendor_name = config["vendor"]
        vendor_cfg  = VENDORS[vendor_name]
        protocol    = config["protocol"]

        self._sidebar.set_busy(True)
        self._sidebar.set_progress(0)
        self._sidebar.set_status("Connecting…", theme.ACCENT)
        self._export_btn.configure(state="disabled")
        self._results_table.clear()
        self._poll_results = []
        self._navigate("poll")

        device_type = (
            vendor_cfg["device_type_telnet"]
            if protocol == "Telnet"
            else vendor_cfg["device_type_ssh"]
        )
        creds = Credentials(
            username=config["username"],
            password=config["password"],
        )

        thread = threading.Thread(
            target=self._poll_worker,
            args=(config["hosts"], creds, device_type,
                  vendor_cfg["collector"], vendor_cfg["parser"]),
            daemon=True,
        )
        thread.start()

    def _poll_worker(
        self,
        hosts: list[str],
        creds: Credentials,
        device_type: str,
        collector,
        parser,
    ) -> None:
        """
        Runs in a background thread — never touches the GUI directly.
        Posts messages to _msg_queue for the main thread to consume.
        """
        results = []
        errors  = []
        total   = len(hosts)

        for idx, host in enumerate(hosts):
            self._msg_queue.put(("status", f"Connecting to {host}…", theme.ACCENT))
            target = SwitchTarget(host=host, credentials=creds)
            try:
                connection = open_session(target, device_type=device_type)
                self._msg_queue.put(("status", f"Collecting data from {host}…", theme.ACCENT))
                raw    = collector.collect(connection, host)
                connection.disconnect()
                parsed = parser.parse(raw)
                results.append(parsed)
                up    = sum(1 for i in parsed.interfaces if i.link.lower() == "up")
                total_ports = len(parsed.interfaces)
                self._msg_queue.put((
                    "status",
                    f"✓ {host} — {up}/{total_ports} ports up",
                    theme.LINK_UP,
                ))
            except SessionError as exc:
                errors.append((host, str(exc)))
                self._msg_queue.put(("status", f"✗ {host} — {exc}", theme.LINK_DOWN))

            self._msg_queue.put(("progress", (idx + 1) / total))

        self._msg_queue.put(("done", results, errors))

    def _drain_message_queue(self) -> None:
        """
        Called every 100 ms on the main thread.
        Applies any pending GUI updates posted by the worker thread.
        """
        try:
            while True:
                msg  = self._msg_queue.get_nowait()
                kind = msg[0]
                if kind == "status":
                    self._sidebar.set_status(msg[1], msg[2])
                elif kind == "progress":
                    self._sidebar.set_progress(msg[1])
                elif kind == "done":
                    self._on_poll_finished(msg[1], msg[2])
        except queue.Empty:
            pass
        self.after(100, self._drain_message_queue)

    def _on_poll_finished(
        self, results: list[ParsedSwitchData], errors: list[tuple[str, str]]
    ) -> None:
        self._sidebar.set_busy(False)
        self._poll_results = results

        if results:
            self._results_table.populate(results)
            self._export_btn.configure(state="normal")
            summary = f"Done — {len(results)} switch(es) polled"
            if errors:
                summary += f", {len(errors)} failed"
            self._sidebar.set_status(summary, theme.LINK_UP)
        else:
            self._sidebar.set_status(
                "No data collected — check IPs and credentials.",
                theme.LINK_DOWN,
            )

        if errors:
            error_text = "\n".join(f"• {host}: {msg}" for host, msg in errors)
            messagebox.showerror("Connection Errors", f"Failed to connect to:\n\n{error_text}")

    # ── Export ─────────────────────────────────────────────────────────────

    def _export(self) -> None:
        if not self._poll_results:
            return
        stamp        = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"pint_live_export_{stamp}.xlsx"

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
            title="Save PiNT Live Export",
        )
        if not path:
            return

        try:
            saved = excel_exporter.export(self._poll_results, Path(path))
            messagebox.showinfo("Export Complete", f"Workbook saved:\n{saved}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = PintLiveApp()
    app.mainloop()


if __name__ == "__main__":
    main()
