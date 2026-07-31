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
from netmiko.exceptions import ReadTimeout

from pint_live.arp          import ArpTable, ArpLoadError, load_arp_xlsx_many
from pint_live.core.session import Credentials, SwitchTarget, open_session, SessionError
from pint_live.core.polling import PollCancelled
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
        self._arp_table: ArpTable | None = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()

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
        self._sidebar.on_arp_load       = self._load_arp_file
        self._sidebar.on_arp_clear      = self._clear_arp_table
        self._sidebar.on_stop_requested = self._stop_poll

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
        Each switch carries its own vendor and resolved credentials, so
        we resolve device_type/collector/parser per switch here.
        """
        protocol = config["protocol"]

        self._stop_event.clear()

        self._sidebar.set_busy(True)
        self._sidebar.set_progress(0)
        self._sidebar.set_status("Connecting…", theme.ACCENT)
        self._export_btn.configure(state="disabled")
        self._results_table.clear()
        self._poll_results = []
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
        self._sidebar.set_busy(False)
        self._poll_results = results

        if results:
            self._results_table.populate(results)
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

        if errors:
            error_text = "\n".join(f"• {host}: {msg}" for host, msg in errors)
            messagebox.showerror("Polling Errors", f"Some switches failed:\n\n{error_text}")

    # ── ARP list ───────────────────────────────────────────────────────────

    def _apply_arp_table(self, table: ArpTable | None) -> None:
        """Push the current ARP table into widgets that render it."""
        self._results_table.set_arp_table(table)
        if self._poll_results:
            self._results_table.populate(self._poll_results)

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
        if not self._poll_results:
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
