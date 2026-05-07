"""PiNT Live — desktop GUI."""

import threading
import queue
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import customtkinter as ctk

from pint_live.core.session import Credentials, SwitchTarget, open_session, SessionError
from pint_live.collectors import ruckus as ruckus_collector
from pint_live.parsers import ruckus as ruckus_parser
from pint_live.exporters import excel as excel_exporter
from pint_live.parsers.ruckus import ParsedSwitchData

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VENDORS = {
    "Ruckus":    {"supported": True,  "device_type_ssh": "ruckus_fastiron",        "device_type_telnet": "ruckus_fastiron_telnet"},
    "Cisco IOS": {"supported": False, "device_type_ssh": "cisco_ios",              "device_type_telnet": "cisco_ios_telnet"},
    "HP/Aruba":  {"supported": False, "device_type_ssh": "hp_procurve",            "device_type_telnet": "hp_procurve_telnet"},
}

COLOUR_UP       = "#2d6a4f"
COLOUR_DOWN     = "#9b2226"
COLOUR_DISABLED = "#495057"


# ---------------------------------------------------------------------------
# Switch IP row widget
# ---------------------------------------------------------------------------

class SwitchRow(ctk.CTkFrame):
    def __init__(self, master, on_remove, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.entry = ctk.CTkEntry(self, placeholder_text="e.g. 192.168.1.1", width=260)
        self.entry.pack(side="left", padx=(0, 6))
        self.remove_btn = ctk.CTkButton(
            self, text="−", width=30, height=28,
            fg_color="#9b2226", hover_color="#ae2012",
            command=on_remove,
        )
        self.remove_btn.pack(side="left")

    @property
    def value(self) -> str:
        return self.entry.get().strip()


# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------

class ResultsTable(ctk.CTkScrollableFrame):
    COLUMNS = ["Interface", "Link", "Speed", "Duplex", "Untagged VLAN", "Tagged VLANs", "MAC(s)", "Description"]
    COL_WIDTHS = [90, 60, 60, 70, 130, 200, 160, 180]

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._draw_headers()

    def _draw_headers(self):
        for col, (header, width) in enumerate(zip(self.COLUMNS, self.COL_WIDTHS)):
            lbl = ctk.CTkLabel(
                self, text=header, font=ctk.CTkFont(size=11, weight="bold"),
                width=width, anchor="w",
            )
            lbl.grid(row=0, column=col, padx=(4, 8), pady=(2, 4), sticky="w")

    def _section_header(self, row_idx: int, text: str):
        lbl = ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#90e0ef",
            anchor="w",
        )
        lbl.grid(row=row_idx, column=0, columnspan=len(self.COLUMNS),
                 padx=4, pady=(10, 2), sticky="w")

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._draw_headers()

    def populate(self, all_data: list[ParsedSwitchData]):
        self.clear()
        row_idx = 1

        port_macs: dict[str, dict[str, list[str]]] = {}
        for data in all_data:
            pm: dict[str, list[str]] = {}
            for entry in data.mac_table:
                pm.setdefault(entry.port, []).append(entry.mac)
            port_macs[data.host] = pm

        for data in all_data:
            self._section_header(
                row_idx,
                f"  {data.hostname or data.host}  ({data.host})  —  {data.model or 'Ruckus ICX'}  fw {data.firmware}",
            )
            row_idx += 1

            for intf in data.interfaces:
                link_lower = intf.link.lower()
                if link_lower == "up":
                    text_colour = "#74c69d"
                elif link_lower == "disabled":
                    text_colour = "#adb5bd"
                else:
                    text_colour = "#e63946"

                macs = ", ".join(port_macs[data.host].get(intf.port, []))
                values = [
                    intf.port, intf.link, intf.speed, intf.duplex,
                    intf.untagged_vlan, intf.tagged_vlans, macs, intf.description,
                ]
                for col, (val, width) in enumerate(zip(values, self.COL_WIDTHS)):
                    colour = text_colour if col == 1 else "#dee2e6"
                    lbl = ctk.CTkLabel(
                        self, text=val, width=width, anchor="w",
                        font=ctk.CTkFont(size=10), text_color=colour,
                    )
                    lbl.grid(row=row_idx, column=col, padx=(4, 8), pady=1, sticky="w")
                row_idx += 1


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class PintApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PiNT Live")
        self.geometry("900x740")
        self.minsize(800, 600)
        self.resizable(True, True)

        self._switch_rows: list[SwitchRow] = []
        self._protocol = tk.StringVar(value="SSH")
        self._vendor = tk.StringVar(value="Ruckus")
        self._use_shared_creds = tk.BooleanVar(value=True)
        self._poll_results: list[ParsedSwitchData] = []
        self._msg_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._add_switch_row()
        self._poll_queue()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Title bar
        title_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a2e")
        title_frame.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            title_frame, text="PiNT Live",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="#90e0ef",
        ).pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(
            title_frame, text="Pi Network Tools — Live",
            font=ctk.CTkFont(size=12), text_color="#6c757d",
        ).pack(side="left", pady=10)

        # Config panel
        config_frame = ctk.CTkFrame(self)
        config_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 4))
        config_frame.grid_columnconfigure(1, weight=1)

        # — Switch IPs
        ctk.CTkLabel(config_frame, text="Switch IPs", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="nw", padx=(12, 16), pady=(12, 4))
        self._switches_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        self._switches_frame.grid(row=0, column=1, sticky="ew", pady=(12, 4))

        add_btn = ctk.CTkButton(
            config_frame, text="+ Add Switch", width=110, height=28,
            command=self._add_switch_row,
        )
        add_btn.grid(row=1, column=1, sticky="w", padx=0, pady=(0, 8))

        sep = ctk.CTkFrame(config_frame, height=1, fg_color="#333")
        sep.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        # — Protocol
        ctk.CTkLabel(config_frame, text="Protocol", font=ctk.CTkFont(weight="bold")).grid(
            row=3, column=0, sticky="w", padx=(12, 16), pady=8)
        proto_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        proto_frame.grid(row=3, column=1, sticky="w", pady=8)

        self._ssh_btn = ctk.CTkButton(
            proto_frame, text="SSH", width=80,
            command=lambda: self._select_protocol("SSH"),
        )
        self._ssh_btn.pack(side="left", padx=(0, 6))

        self._telnet_btn = ctk.CTkButton(
            proto_frame, text="Telnet", width=80,
            fg_color="#495057", hover_color="#6c757d",
            command=lambda: self._select_protocol("Telnet"),
        )
        self._telnet_btn.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            proto_frame, text="⚠ Unencrypted",
            font=ctk.CTkFont(size=11), text_color="#f4a261",
        ).pack(side="left")

        sep2 = ctk.CTkFrame(config_frame, height=1, fg_color="#333")
        sep2.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        # — Vendor
        ctk.CTkLabel(config_frame, text="Vendor", font=ctk.CTkFont(weight="bold")).grid(
            row=5, column=0, sticky="w", padx=(12, 16), pady=8)
        vendor_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        vendor_frame.grid(row=5, column=1, sticky="w", pady=8)
        self._vendor_buttons: dict[str, ctk.CTkButton] = {}
        for name in VENDORS:
            btn = ctk.CTkButton(
                vendor_frame, text=name, width=100,
                fg_color="#1d3557", hover_color="#457b9d",
                command=lambda n=name: self._select_vendor(n),
            )
            btn.pack(side="left", padx=(0, 6))
            self._vendor_buttons[name] = btn
        self._select_vendor("Ruckus")

        sep3 = ctk.CTkFrame(config_frame, height=1, fg_color="#333")
        sep3.grid(row=6, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        # — Credentials
        ctk.CTkLabel(config_frame, text="Username", font=ctk.CTkFont(weight="bold")).grid(
            row=7, column=0, sticky="w", padx=(12, 16), pady=(8, 4))
        self._username_entry = ctk.CTkEntry(config_frame, width=220, placeholder_text="admin")
        self._username_entry.grid(row=7, column=1, sticky="w", pady=(8, 4))

        ctk.CTkLabel(config_frame, text="Password", font=ctk.CTkFont(weight="bold")).grid(
            row=8, column=0, sticky="w", padx=(12, 16), pady=(4, 8))
        self._password_entry = ctk.CTkEntry(config_frame, width=220, show="●")
        self._password_entry.grid(row=8, column=1, sticky="w", pady=(4, 8))

        ctk.CTkCheckBox(
            config_frame,
            text="Use these credentials for all switches",
            variable=self._use_shared_creds,
        ).grid(row=9, column=1, sticky="w", pady=(0, 12))

        # Poll button
        self._poll_btn = ctk.CTkButton(
            self, text="Poll Switches", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_poll,
        )
        self._poll_btn.grid(row=2, column=0, sticky="ew", padx=12, pady=6)

        # Status bar
        self._status_label = ctk.CTkLabel(
            self, text="Ready.", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#6c757d",
        )
        self._status_label.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 2))

        # Progress bar
        self._progress = ctk.CTkProgressBar(self)
        self._progress.set(0)
        self._progress.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 4))

        # Results table
        self._results_table = ResultsTable(self, label_text="Results", fg_color="#1e1e2e")
        self._results_table.grid(row=5, column=0, sticky="nsew", padx=12, pady=4)

        # Export button
        self._export_btn = ctk.CTkButton(
            self, text="Export to Excel", height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2d6a4f", hover_color="#40916c",
            state="disabled",
            command=self._export,
        )
        self._export_btn.grid(row=6, column=0, sticky="ew", padx=12, pady=(4, 12))

    # -----------------------------------------------------------------------
    # Switch row management
    # -----------------------------------------------------------------------

    def _add_switch_row(self):
        row = SwitchRow(self._switches_frame, on_remove=lambda r=None: self._remove_switch_row(r))
        row._remove_callback = lambda: self._remove_switch_row(row)
        row.remove_btn.configure(command=row._remove_callback)
        row.pack(anchor="w", pady=2)
        self._switch_rows.append(row)

    def _remove_switch_row(self, row: SwitchRow):
        if len(self._switch_rows) == 1:
            return
        self._switch_rows.remove(row)
        row.destroy()

    # -----------------------------------------------------------------------
    # Protocol / vendor selection
    # -----------------------------------------------------------------------

    def _select_protocol(self, proto: str):
        if proto == "Telnet":
            confirmed = messagebox.askyesno(
                "Security Warning",
                "Are you sure you want to use Telnet?\n\n"
                "Telnet is not a secure method of connecting to devices over the network. "
                "All data, including your credentials and switch output, will be transmitted "
                "in plaintext and could be intercepted.\n\n"
                "SSH is strongly recommended.",
                icon="warning",
            )
            if not confirmed:
                return

        self._protocol.set(proto)
        if proto == "SSH":
            self._ssh_btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            self._telnet_btn.configure(fg_color="#495057")
        else:
            self._ssh_btn.configure(fg_color="#495057")
            self._telnet_btn.configure(fg_color="#ae2012")

    def _select_vendor(self, name: str):
        self._vendor.set(name)
        for vendor_name, btn in self._vendor_buttons.items():
            if vendor_name == name:
                btn.configure(fg_color="#457b9d")
            else:
                btn.configure(fg_color="#1d3557")

    # -----------------------------------------------------------------------
    # Polling
    # -----------------------------------------------------------------------

    def _start_poll(self):
        vendor_name = self._vendor.get()
        if not VENDORS[vendor_name]["supported"]:
            messagebox.showinfo(
                "Coming Soon",
                f"{vendor_name} support is not yet available in this version of PiNT Live.\n\n"
                "Only Ruckus ICX is supported right now. More vendors are coming soon.",
            )
            return

        hosts = [r.value for r in self._switch_rows if r.value]
        if not hosts:
            messagebox.showwarning("No Switches", "Please enter at least one switch IP or hostname.")
            return

        username = self._username_entry.get().strip()
        password = self._password_entry.get()
        if not username or not password:
            messagebox.showwarning("Missing Credentials", "Please enter a username and password.")
            return

        self._poll_btn.configure(state="disabled", text="Polling...")
        self._export_btn.configure(state="disabled")
        self._results_table.clear()
        self._poll_results = []
        self._progress.set(0)
        self._status("Connecting...", colour="#90e0ef")

        protocol = self._protocol.get()
        use_telnet = protocol == "Telnet"
        device_type_key = "device_type_telnet" if use_telnet else "device_type_ssh"
        device_type = VENDORS[vendor_name][device_type_key]

        creds = Credentials(username=username, password=password)
        thread = threading.Thread(
            target=self._poll_worker,
            args=(hosts, creds, device_type),
            daemon=True,
        )
        thread.start()

    def _poll_worker(self, hosts: list[str], creds: Credentials, device_type: str):
        results = []
        errors = []
        total = len(hosts)

        for idx, host in enumerate(hosts):
            self._msg_queue.put(("status", f"Connecting to {host}...", "#90e0ef"))
            target = SwitchTarget(host=host, credentials=creds)
            try:
                connection = open_session(target, device_type=device_type)
                self._msg_queue.put(("status", f"Collecting data from {host}...", "#90e0ef"))
                raw = ruckus_collector.collect(connection, host)
                connection.disconnect()
                parsed = ruckus_parser.parse(raw)
                results.append(parsed)
                up = sum(1 for i in parsed.interfaces if i.link.lower() == "up")
                total_ports = len(parsed.interfaces)
                self._msg_queue.put(("status", f"✓ {host} — {up}/{total_ports} ports up", "#74c69d"))
            except SessionError as exc:
                errors.append((host, str(exc)))
                self._msg_queue.put(("status", f"✗ {host} — {exc}", "#e63946"))

            self._msg_queue.put(("progress", (idx + 1) / total, None))

        self._msg_queue.put(("done", results, errors))

    def _poll_queue(self):
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                kind = msg[0]
                if kind == "status":
                    self._status(msg[1], colour=msg[2])
                elif kind == "progress":
                    self._progress.set(msg[1])
                elif kind == "done":
                    self._poll_finished(msg[1], msg[2])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _poll_finished(self, results: list[ParsedSwitchData], errors: list):
        self._poll_results = results
        self._poll_btn.configure(state="normal", text="Poll Switches")

        if results:
            self._results_table.populate(results)
            self._export_btn.configure(state="normal")
            summary = f"Done — {len(results)} switch(es) polled"
            if errors:
                summary += f", {len(errors)} failed"
            self._status(summary, colour="#74c69d")
        else:
            self._status("No data collected — check IPs and credentials.", colour="#e63946")

        if errors:
            error_text = "\n".join(f"• {h}: {m}" for h, m in errors)
            messagebox.showerror("Connection Errors", f"Failed to connect to:\n\n{error_text}")

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def _export(self):
        if not self._poll_results:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"pint_export_{stamp}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
            title="Save PiNT Export",
        )
        if not path:
            return
        try:
            saved = excel_exporter.export(self._poll_results, Path(path))
            messagebox.showinfo("Export Complete", f"Workbook saved to:\n{saved}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _status(self, text: str, colour: str = "#6c757d"):
        self._status_label.configure(text=text, text_color=colour)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = PintApp()
    app.mainloop()


if __name__ == "__main__":
    main()
