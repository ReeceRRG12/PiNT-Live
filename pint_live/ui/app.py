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
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from netmiko.exceptions import ReadTimeout

from pint_live.arp          import ArpTable, ArpLoadError, load_arp_xlsx_many
from pint_live.core.session import Credentials, SwitchTarget, open_session, SessionError
from pint_live.core.polling import PollCancelled
from pint_live.exporters    import excel as excel_exporter
from pint_live.models       import ParsedSwitchData
from pint_live import __version__
from pint_live.vendors      import REGISTRY as VENDORS

from pint_live.ui            import theme
from pint_live.ui            import assets
from pint_live.ui.scale_manager import initial_window_size
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
        width, height = initial_window_size(self)
        self.geometry(f"{width}x{height}")
        self.minsize(min(980, width), min(620, height))
        self.resizable(True, True)
        self.configure(fg_color=theme.BG)

        # App state
        self._poll_results: list[ParsedSwitchData] = []
        self._arp_table: ArpTable | None = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._search_after = None
        self._polling = False

        self._build_layout()
        assets.set_taskbar_icon(self)

        # Start with the poll view active
        self._navigate("poll")
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.bind(f"<{modifier}-f>", self._focus_search)
        self.bind(f"<{modifier}-e>", lambda event: self._export())

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
        self._sidebar.on_arp_load       = self._load_arp_file
        self._sidebar.on_arp_clear      = self._clear_arp_table
        self._sidebar.on_stop_requested = self._stop_poll

        # ── Content area (right, fills remaining space) ────────────────────
        self._content = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        # Results view = table + export button
        self._results_view = ctk.CTkFrame(self._content, fg_color=theme.BG, corner_radius=0)
        self._results_view.place(relwidth=1, relheight=1)

        header = ctk.CTkFrame(self._results_view, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(26, 18))
        ctk.CTkLabel(
            header, text=f"v{__version__}", font=theme.font_body(12),
            text_color=theme.ACCENT, fg_color=theme.NAV_ACTIVE_BG,
            corner_radius=8, width=94, height=30,
        ).pack(side="right", anchor="n", pady=4)
        ctk.CTkLabel(
            header, text="Network overview", font=theme.font_heading(28),
            text_color=theme.TEXT_PRIMARY, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            header, text="Live switch data. Clear network documentation.",
            font=theme.font_body(13), text_color=theme.TEXT_MUTED, anchor="w",
        ).pack(fill="x", pady=(4, 0))

        metrics = ctk.CTkFrame(self._results_view, fg_color="transparent")
        metrics.pack(fill="x", padx=24, pady=(0, 20))
        self._metric_values = {}
        for column, (key, label, color) in enumerate([
            ("switches", "SWITCHES", theme.TEXT_PRIMARY),
            ("ports", "PORTS", theme.TEXT_PRIMARY),
            ("up", "LINKS UP", theme.LINK_UP),
            ("macs", "MAC ENTRIES", theme.ACCENT),
        ]):
            metrics.grid_columnconfigure(column, weight=1, uniform="metric")
            card = ctk.CTkFrame(metrics, fg_color=theme.PANEL_BG, corner_radius=10)
            card.grid(row=0, column=column, sticky="ew", padx=(0, 10 if column < 3 else 0))
            value = ctk.CTkLabel(card, text="—", text_color=color, font=theme.font_heading(26), anchor="w")
            value.pack(fill="x", padx=16, pady=(12, 0))
            ctk.CTkLabel(card, text=label, text_color=theme.TEXT_MUTED, font=theme.font_bold(11), anchor="w").pack(fill="x", padx=16, pady=(0, 10))
            self._metric_values[key] = value

        toolbar = ctk.CTkFrame(self._results_view, fg_color="transparent")
        toolbar.pack(fill="x", padx=24, pady=(0, 10))
        self._search = ctk.CTkEntry(
            toolbar, placeholder_text="Search switch, port, VLAN, MAC or description…",
            font=theme.font_body(13), height=38, fg_color=theme.PANEL_BG,
            border_color=theme.SEPARATOR,
        )
        self._search.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self._search.bind("<KeyRelease>", self._schedule_filter)
        self._link_filter = ctk.CTkOptionMenu(
            toolbar, values=["All ports", "Up", "Down", "Disabled"], width=132, height=38,
            font=theme.font_body(13), fg_color=theme.NAV_INACTIVE_BG,
            button_color=theme.SEPARATOR, button_hover_color=theme.NAV_ACTIVE_BG,
            command=lambda value: self._refresh_results(),
        )
        self._table_area = ctk.CTkFrame(self._results_view, fg_color=theme.PANEL_BG, corner_radius=10)
        self._table_area.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self._results_table = ResultsTable(self._table_area)
        self._results_table.pack(fill="both", expand=True)
        self._link_filter.pack(side="right")

        self._empty_state = ctk.CTkFrame(self._table_area, fg_color=theme.PANEL_BG, corner_radius=10)
        self._empty_title = ctk.CTkLabel(self._empty_state, text="Your network, at a glance", font=theme.font_heading(22), text_color=theme.TEXT_PRIMARY)
        self._empty_title.pack(pady=(0, 10))
        self._empty_description = ctk.CTkLabel(
            self._empty_state,
            text="1  Add your switches and choose their vendors.\n2  Set credentials, then start polling.\n3  Review your ports and export an Excel workbook.",
            font=theme.font_body(14), text_color=theme.TEXT_MUTED,
            justify="left", wraplength=440,
        )
        self._empty_description.pack()
        self._empty_state.place(relx=0.5, rely=0.5, anchor="center")

        footer = ctk.CTkFrame(self._results_view, fg_color="transparent")
        # Reserve the footer before the expanding table so export stays
        # reachable even when the window is reduced to its minimum height.
        footer.pack(side="bottom", fill="x", padx=24, pady=(0, 20), before=self._table_area)
        self._results_caption = ctk.CTkLabel(
            footer, text="Ready for your first poll", anchor="w",
            font=theme.font_body(12), text_color=theme.TEXT_MUTED,
        )
        self._results_caption.pack(side="left", fill="x", expand=True)

        self._export_btn = ctk.CTkButton(
            footer,
            text="Export to Excel",
            height=40,
            width=160,
            font=theme.font_bold(13),
            fg_color=theme.EXPORT_BTN_BG,
            hover_color=theme.EXPORT_BTN_HOVER,
            corner_radius=theme.CORNER_R,
            state="disabled",
            command=self._export,
        )
        self._export_btn.pack(side="right", padx=(12, 0), before=self._results_caption)

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

    def _focus_search(self, event=None):
        self._navigate("poll")
        self._search.focus_set()
        self._search.select_range(0, "end")
        return "break"

    def _schedule_filter(self, event=None) -> None:
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(180, self._refresh_results)

    def _refresh_results(self) -> None:
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = None
        if self._polling:
            return
        shown = self._results_table.populate(
            self._poll_results, self._search.get(), self._link_filter.get(),
        )
        total = sum(len(switch.interfaces) for switch in self._poll_results)
        self._results_caption.configure(text=f"{shown:,} of {total:,} ports shown · Export includes all results")
        if shown:
            self._empty_state.place_forget()
        elif self._poll_results:
            self._empty_title.configure(text="No matching ports")
            self._empty_description.configure(text="Try a different search or choose All ports.")
            self._empty_state.place(relx=0.5, rely=0.5, anchor="center")

    def _update_metrics(self) -> None:
        values = {
            "switches": len(self._poll_results),
            "ports": sum(len(s.interfaces) for s in self._poll_results),
            "up": sum(i.link.lower() == "up" for s in self._poll_results for i in s.interfaces),
            "macs": sum(len(s.mac_table) for s in self._poll_results),
        }
        for key, value in values.items():
            self._metric_values[key].configure(text=f"{value:,}")

    def _start_poll(self, config: dict) -> None:
        """
        Called by the sidebar when the user clicks Poll Switches.
        Each switch carries its own vendor and resolved credentials, so
        we resolve device_type/collector/parser per switch here.
        """
        protocol = config["protocol"]
        self._polling = True

        self._stop_event.clear()

        self._sidebar.set_busy(True)
        self._sidebar.set_progress(0)
        self._sidebar.set_status("Connecting…", theme.ACCENT)
        self._export_btn.configure(state="disabled")
        self._results_table.clear()
        self._poll_results = []
        self._search.delete(0, "end")
        self._link_filter.set("All ports")
        self._update_metrics()
        self._empty_title.configure(text="Discovering your network…")
        self._empty_description.configure(text="Results appear when polling finishes.\nYou can stop at any time and keep completed switches.")
        self._empty_state.place(relx=0.5, rely=0.5, anchor="center")
        self._results_caption.configure(text="Polling in progress")
        self._navigate("poll")

        # Build a per-switch job list the worker can iterate over without
        # needing access to the vendor registry itself.
        jobs = []
        for sw in config["switches"]:
            vendor_cfg = VENDORS[sw["vendor"]]
            device_type = (
                vendor_cfg["device_type_telnet"]
                if protocol == "Telnet"
                else vendor_cfg["device_type_ssh"]
            )
            jobs.append({
                "host":        sw["host"],
                "vendor":      sw["vendor"],
                "device_type": device_type,
                "collector":   vendor_cfg["collector"],
                "parser":      vendor_cfg["parser"],
                "credentials": Credentials(
                    username=sw["username"],
                    password=sw["password"],
                ),
            })

        thread = threading.Thread(
            target=self._poll_worker,
            args=(jobs,),
            daemon=True,
        )
        thread.start()

    def _poll_worker(self, jobs: list[dict]) -> None:
        """
        Runs in a background thread — never touches the GUI directly.
        Posts messages to _msg_queue for the main thread to consume.
        """
        results: list[ParsedSwitchData] = []
        errors: list[tuple[str, str]] = []
        total = len(jobs)
        stopped = False

        try:
            for idx, job in enumerate(jobs):
                if self._stop_event.is_set():
                    stopped = True
                    break

                host = job["host"]
                target = SwitchTarget(host=host, credentials=job["credentials"])

                # A transient VPN/SSH read failure gets one fresh connection.
                for attempt in range(1, 3):
                    connection = None
                    try:
                        retry = " (retry)" if attempt == 2 else ""
                        self._msg_queue.put((
                            "status",
                            f"Connecting to {host} ({job['vendor']}){retry}…",
                            theme.ACCENT,
                        ))
                        connection = open_session(target, device_type=job["device_type"])
                        self._msg_queue.put((
                            "status", f"Collecting data from {host}{retry}…", theme.ACCENT,
                        ))
                        raw = job["collector"].collect(
                            connection, host, self._stop_event.is_set,
                        )
                        parsed = job["parser"].parse(raw)
                        if not parsed.interfaces:
                            raise ValueError("No interfaces were recognised in the switch output")
                        results.append(parsed)
                        up = sum(1 for i in parsed.interfaces if i.link.lower() == "up")
                        self._msg_queue.put((
                            "status",
                            f"✓ {host} — {up}/{len(parsed.interfaces)} ports up",
                            theme.LINK_UP,
                        ))
                        break
                    except PollCancelled:
                        stopped = True
                        break
                    except ReadTimeout as exc:
                        if attempt == 1 and not self._stop_event.is_set():
                            self._msg_queue.put((
                                "status", f"Retrying {host} after a response timeout…", theme.WARNING,
                            ))
                            continue
                        message = self._friendly_poll_error(exc)
                        errors.append((host, message))
                        self._msg_queue.put(("status", f"✗ {host} — {message}", theme.LINK_DOWN))
                        break
                    except Exception as exc:
                        message = self._friendly_poll_error(exc)
                        errors.append((host, message))
                        self._msg_queue.put(("status", f"✗ {host} — {message}", theme.LINK_DOWN))
                        break
                    finally:
                        if connection is not None:
                            try:
                                connection.disconnect()
                            except Exception:
                                pass

                self._msg_queue.put(("progress", (idx + 1) / total))
                if stopped:
                    break
        except Exception as exc:
            # Last-resort guard: the UI must never remain permanently busy.
            errors.append(("Poll worker", self._friendly_poll_error(exc)))
        finally:
            self._msg_queue.put(("done", results, errors, stopped))

    @staticmethod
    def _friendly_poll_error(exc: Exception) -> str:
        if isinstance(exc, ReadTimeout):
            return "Timed out waiting for the switch response"
        message = next((line.strip() for line in str(exc).splitlines() if line.strip()), "")
        return message or type(exc).__name__

    def _stop_poll(self) -> None:
        """Request a cooperative stop between CLI commands or switches."""
        self._stop_event.set()
        self._sidebar.set_stop_requested()
        self._sidebar.set_status(
            "Stopping… waiting for the current command to finish.", theme.WARNING,
        )

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
                    self._on_poll_finished(msg[1], msg[2], msg[3])
        except queue.Empty:
            pass
        self.after(100, self._drain_message_queue)

    def _on_poll_finished(
        self,
        results: list[ParsedSwitchData],
        errors: list[tuple[str, str]],
        stopped: bool = False,
    ) -> None:
        self._polling = False
        self._sidebar.set_busy(False)
        self._poll_results = results
        self._update_metrics()

        if results:
            self._refresh_results()
            self._export_btn.configure(state="normal")
            summary = (
                f"Stopped — {len(results)} switch(es) completed"
                if stopped else f"Done — {len(results)} switch(es) polled"
            )
            if errors:
                summary += f", {len(errors)} failed"
            self._sidebar.set_status(summary, theme.WARNING if stopped else theme.LINK_UP)
        else:
            message = (
                "Stopped — no switches completed."
                if stopped else "No data collected — check IPs and credentials."
            )
            self._sidebar.set_status(message, theme.WARNING if stopped else theme.LINK_DOWN)
            self._empty_title.configure(text="Poll stopped" if stopped else "No data collected")
            self._empty_description.configure(text=message)
            self._results_caption.configure(text="No results to export")

        if errors:
            error_text = "\n".join(f"• {host}: {msg}" for host, msg in errors)
            messagebox.showerror("Polling Errors", f"Some switches failed:\n\n{error_text}")

    # ── ARP list ───────────────────────────────────────────────────────────

    def _apply_arp_table(self, table: ArpTable | None) -> None:
        """Push the current ARP table into widgets that render it."""
        self._results_table.set_arp_table(table)
        if self._poll_results:
            self._refresh_results()

    def _load_arp_file(self) -> ArpTable | None:
        """Prompt for one or more ARP .xlsx files and append them to the
        currently loaded set. Returns the merged table (or None on cancel /
        if nothing usable was loaded)."""
        paths = filedialog.askopenfilenames(
            filetypes=[("Excel workbook", "*.xlsx")],
            title="Load ARP List(s) — select one or more",
        )
        if not paths:
            return None

        new_table, errors = load_arp_xlsx_many(paths)

        if errors:
            error_text = "\n".join(f"• {p.name}: {msg}" for p, msg in errors)
            messagebox.showerror(
                "ARP Load Failed",
                f"Some files could not be loaded:\n\n{error_text}",
            )

        if not new_table.entries:
            if not errors:
                messagebox.showwarning(
                    "ARP List Empty",
                    "No usable IP/MAC rows were found in the selected file(s).",
                )
            # Even on full failure, fall through so existing state is unchanged.
            return self._arp_table

        if self._arp_table is None:
            self._arp_table = new_table
        else:
            self._arp_table.extend(new_table)

        self._refresh_arp_status()
        self._apply_arp_table(self._arp_table)
        return self._arp_table

    def _clear_arp_table(self) -> None:
        self._arp_table = None
        self._sidebar.set_arp_status("No ARP lists loaded.", loaded=False)
        self._apply_arp_table(None)

    def _refresh_arp_status(self) -> None:
        """Push the current ARP table summary to the sidebar status line."""
        if self._arp_table is None or not self._arp_table.entries:
            self._sidebar.set_arp_status("No ARP lists loaded.", loaded=False)
            return
        n_files = self._arp_table.file_count
        n_rows  = len(self._arp_table)
        if n_files == 1:
            label = f"{self._arp_table.source_paths[0].name} — {n_rows} entries"
        else:
            label = f"{n_files} files — {n_rows} entries"
        self._sidebar.set_arp_status(label, loaded=True)

    # ── Export ─────────────────────────────────────────────────────────────

    def _export(self) -> None:
        if self._polling or not self._poll_results:
            return

        arp_table = self._resolve_arp_for_export()

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
            saved = excel_exporter.export(
                self._poll_results,
                Path(path),
                arp_table=arp_table,
                include_raw_outputs=self._sidebar.include_raw_outputs,
            )
            messagebox.showinfo("Export Complete", f"Workbook saved:\n{saved}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    def _resolve_arp_for_export(self) -> ArpTable | None:
        """Decide which ARP table (if any) to use for this export.

        If lists are already loaded, offer to use them, load more first, or
        skip. If none are loaded, offer to load some now or skip."""
        if self._arp_table is not None and self._arp_table.entries:
            n_files = self._arp_table.file_count
            descriptor = (
                f"{n_files} files, {len(self._arp_table)} entries"
                if n_files != 1
                else f"{self._arp_table.source_paths[0].name}, "
                     f"{len(self._arp_table)} entries"
            )
            choice = messagebox.askyesnocancel(
                "ARP Lists",
                f"Use the currently loaded ARP data ({descriptor}) "
                f"to add IP/Hostname columns?\n\n"
                "Yes  → use the loaded data\n"
                "No   → load more ARP file(s) first, then use everything\n"
                "Cancel → export without IP/Hostname columns",
            )
            if choice is None:
                return None
            if choice is True:
                return self._arp_table
            self._load_arp_file()
            return self._arp_table

        choice = messagebox.askyesno(
            "ARP Lists",
            "Load one or more ARP lists (.xlsx) to add IP and Hostname "
            "columns to each switch tab?",
        )
        if not choice:
            return None
        return self._load_arp_file()


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = PintLiveApp()
    app.mainloop()


if __name__ == "__main__":
    main()
