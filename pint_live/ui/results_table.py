"""
PiNT Live — results table widget.

A scrollable grid that displays polled switch data.
Each switch gets a coloured section header, followed by one row
per interface with link-state colour coding.
"""

from tkinter import ttk

import customtkinter as ctk

from pint_live.arp    import ArpTable
from pint_live.models import ParsedSwitchData
from pint_live.ui import theme


# Column definitions — label and pixel width
_COLUMNS_BASE = [
    ("Interface",     90),
    ("Link",          60),
    ("Speed",         60),
    ("Duplex",        70),
    ("Untagged VLAN", 130),
    ("Tagged VLANs",  200),
    ("MAC(s)",        160),
    ("Description",   180),
]
_COLUMNS_ARP = [
    ("IP (ARP)",       120),
    ("Hostname (ARP)", 150),
]
# When an ARP table is loaded, IP/Hostname are inserted directly after MAC(s).
_MAC_COL_IDX = next(i for i, (label, _) in enumerate(_COLUMNS_BASE) if label == "MAC(s)")


class ResultsTable(ctk.CTkFrame):
    """
    Efficient scrollable results table.

    A single ttk.Treeview stores every row. The previous implementation made
    one CTkLabel per cell, which became thousands of heavyweight Tk widgets
    and could block the UI for many minutes on site-sized polls.

    Usage:
        table = ResultsTable(parent)
        table.populate(list_of_ParsedSwitchData)
        table.clear()
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.PANEL_BG)
        kwargs.setdefault("corner_radius", theme.CORNER_R)
        super().__init__(master, **kwargs)
        self._arp_table: ArpTable | None = None
        self._build_tree()

    # ── Public interface ───────────────────────────────────────────────────

    def set_arp_table(self, arp_table: ArpTable | None) -> None:
        """Set/clear ARP enrichment and update the table columns."""
        self._arp_table = arp_table
        self._configure_columns()

    def clear(self) -> None:
        """Remove all rows without rebuilding any widgets."""
        children = self._tree.get_children()
        if children:
            self._tree.delete(*children)

    def populate(self, all_data: list[ParsedSwitchData]) -> None:
        """Replace the current contents with rows from all_data."""
        self.clear()

        # Pre-build port → MAC lookup for each switch
        port_macs = _build_port_mac_index(all_data)
        arp       = self._arp_table

        for switch in all_data:
            parent = self._tree.insert(
                "",
                "end",
                text=switch.hostname or switch.host,
                values=(switch.host, switch.model or "Unknown", switch.firmware),
                open=True,
                tags=("switch",),
            )

            for intf in switch.interfaces:
                macs_list = port_macs[switch.host].get(intf.port, [])
                macs      = ", ".join(macs_list)
                row_values = [
                    intf.port,
                    intf.link,
                    intf.speed,
                    intf.duplex,
                    intf.untagged_vlan,
                    intf.tagged_vlans,
                    macs,
                ]
                if arp is not None:
                    ips       = arp.resolve_ips(macs_list)
                    hostnames = arp.resolve_hostnames(macs_list)
                    row_values.append(", ".join(ips))
                    row_values.append(", ".join(h for h in hostnames if h))
                row_values.append(intf.description)
                self._tree.insert(
                    parent,
                    "end",
                    text=row_values[0],
                    values=row_values[1:],
                    tags=(_link_tag(intf.link),),
                )

    # ── Private drawing helpers ────────────────────────────────────────────

    def _columns(self) -> list[tuple[str, int]]:
        if self._arp_table is None:
            return _COLUMNS_BASE
        return (
            _COLUMNS_BASE[:_MAC_COL_IDX + 1]
            + _COLUMNS_ARP
            + _COLUMNS_BASE[_MAC_COL_IDX + 1:]
        )

    def _build_tree(self) -> None:
        """Create the one table widget and its two scrollbars."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self)
        style.configure(
            "Pint.Treeview",
            background=theme.PANEL_BG,
            fieldbackground=theme.PANEL_BG,
            foreground=theme.TEXT_PRIMARY,
            rowheight=24,
            borderwidth=0,
            font=("Arial", 10),
        )
        style.map(
            "Pint.Treeview",
            background=[("selected", theme.NAV_ACTIVE_BG)],
            foreground=[("selected", theme.TEXT_PRIMARY)],
        )
        style.configure(
            "Pint.Treeview.Heading",
            background=theme.NAV_INACTIVE_BG,
            foreground=theme.TEXT_PRIMARY,
            relief="flat",
            font=("Arial", 10, "bold"),
        )
        style.map(
            "Pint.Treeview.Heading",
            background=[("active", theme.NAV_ACTIVE_BG)],
        )

        self._tree = ttk.Treeview(
            self,
            show="tree headings",
            style="Pint.Treeview",
            selectmode="browse",
        )
        y_scroll = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self._tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=(4, 0))
        y_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=(4, 0))
        x_scroll.grid(row=1, column=0, sticky="ew", padx=(4, 0), pady=(0, 4))

        self._tree.tag_configure("switch", foreground=theme.ACCENT, font=("Arial", 10, "bold"))
        self._tree.tag_configure("up", foreground=theme.LINK_UP)
        self._tree.tag_configure("down", foreground=theme.LINK_DOWN)
        self._tree.tag_configure("disabled", foreground=theme.LINK_DISABLED)
        self._configure_columns()

    def _configure_columns(self) -> None:
        columns = self._columns()
        value_ids = tuple(f"value_{idx}" for idx in range(1, len(columns)))
        self._tree.configure(columns=value_ids)

        first_label, first_width = columns[0]
        self._tree.heading("#0", text=first_label, anchor="w")
        self._tree.column("#0", width=first_width, minwidth=first_width, stretch=False)

        for column_id, (label, width) in zip(value_ids, columns[1:]):
            self._tree.heading(column_id, text=label, anchor="w")
            self._tree.column(column_id, width=width, minwidth=40, stretch=False)


# ── Module-level helpers ───────────────────────────────────────────────────

def _link_tag(link: str) -> str:
    """Return the Treeview tag that corresponds to a link state."""
    key = link.lower()
    if key == "up":
        return "up"
    if key == "disabled":
        return "disabled"
    return "down"


def _build_port_mac_index(
    all_data: list[ParsedSwitchData],
) -> dict[str, dict[str, list[str]]]:
    """
    Build a nested dict: host → port → [mac, mac, ...].
    Used to quickly look up which MACs were seen on each interface.
    """
    index: dict[str, dict[str, list[str]]] = {}
    for switch in all_data:
        port_map: dict[str, list[str]] = {}
        for entry in switch.mac_table:
            port_map.setdefault(entry.port, []).append(entry.mac)
        index[switch.host] = port_map
    return index
