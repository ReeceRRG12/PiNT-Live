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
    ("Switch / interface", 250),
    ("Link",          85),
    ("Speed",         85),
    ("Duplex",        85),
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

    def populate(
        self, all_data: list[ParsedSwitchData], query: str = "", link_filter: str = "All ports",
    ) -> int:
        """Replace the current contents with rows from all_data."""
        self.clear()

        arp       = self._arp_table

        shown = 0
        for switch in all_data:
            # A host can appear more than once when it was polled repeatedly.
            # Keep each snapshot's MACs with that snapshot's interfaces.
            port_macs = _build_port_mac_index(switch)
            parent = None

            for intf in switch.interfaces:
                macs_list = port_macs.get(intf.port, [])
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
                    row_values.append(", ".join(hostnames))
                row_values.append(intf.description)
                if not _matches_row(switch, row_values, query, link_filter):
                    continue
                if parent is None:
                    name = switch.hostname or switch.host
                    details = " · ".join(
                        value for value in (switch.host if switch.hostname else "", switch.model) if value
                    )
                    parent = self._tree.insert(
                        "", "end", text=f"{name}  {details}".strip(),
                        open=True, tags=("switch",),
                    )
                self._tree.insert(
                    parent,
                    "end",
                    text=row_values[0],
                    values=row_values[1:],
                    tags=(_link_tag(intf.link),),
                )
                shown += 1
        return shown

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

        style = self._style = ttk.Style(self)
        # Aqua and Windows native heading renderers ignore dark background
        # colours. Clam gives the embedded table the same palette on both.
        style.theme_use("clam")
        style.layout("Pint.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Pint.Treeview",
            background=theme.PANEL_BG,
            fieldbackground=theme.PANEL_BG,
            foreground=theme.TEXT_PRIMARY,
            rowheight=32,
            borderwidth=0,
            font=(theme.FONT_FAMILY, 11),
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
            font=(theme.FONT_FAMILY, 11, "bold"),
            padding=(10, 9),
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
        scrollbar_style = dict(
            fg_color=theme.PANEL_BG, button_color=theme.SEPARATOR,
            button_hover_color=theme.ACCENT_HOVER,
        )
        y_scroll = ctk.CTkScrollbar(self, orientation="vertical", command=self._tree.yview, **scrollbar_style)
        x_scroll = ctk.CTkScrollbar(self, orientation="horizontal", command=self._tree.xview, **scrollbar_style)
        self._tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self._tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=(4, 0))
        y_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=(4, 0))
        x_scroll.grid(row=1, column=0, sticky="ew", padx=(4, 0), pady=(0, 4))

        self._tree.tag_configure("switch", foreground=theme.ACCENT, background=theme.NAV_INACTIVE_BG, font=(theme.FONT_FAMILY, 11, "bold"))
        self._tree.tag_configure("up", foreground=theme.LINK_UP)
        self._tree.tag_configure("down", foreground=theme.LINK_DOWN)
        self._tree.tag_configure("disabled", foreground=theme.LINK_DISABLED)
        self._apply_tree_scaling()
        self._configure_columns()

    def _set_scaling(self, *args, **kwargs) -> None:
        super()._set_scaling(*args, **kwargs)
        if "_tree" in self.__dict__:
            self._apply_tree_scaling()
            self._configure_columns()

    def _apply_tree_scaling(self) -> None:
        # ttk is outside CTk's automatic widget scaling. Keep rows, headings
        # and fonts in the same logical units, including monitor DPI changes.
        scale = self._get_widget_scaling()
        font = (theme.FONT_FAMILY, -round(13 * scale))
        self._style.configure("Pint.Treeview", rowheight=round(32 * scale), font=font)
        self._style.configure(
            "Pint.Treeview.Heading", font=(*font, "bold"),
            padding=(round(10 * scale), round(9 * scale)),
        )
        self._tree.tag_configure("switch", font=(*font, "bold"))

    def _configure_columns(self) -> None:
        columns = self._columns()
        scale = self._get_widget_scaling()
        value_ids = tuple(f"value_{idx}" for idx in range(1, len(columns)))
        self._tree.configure(columns=value_ids)

        first_label, first_width = columns[0]
        first_width = round(first_width * scale)
        self._tree.heading("#0", text=first_label, anchor="w")
        self._tree.column("#0", width=first_width, minwidth=first_width, stretch=False)

        for column_id, (label, width) in zip(value_ids, columns[1:]):
            self._tree.heading(column_id, text=label, anchor="w")
            self._tree.column(column_id, width=round(width * scale), minwidth=round(40 * scale), stretch=False)


# ── Module-level helpers ───────────────────────────────────────────────────

def _matches_row(switch, values: list, query: str, link_filter: str) -> bool:
    """Match visible port fields and switch identity, including ARP enrichment."""
    if link_filter != "All ports" and str(values[1]).casefold() != link_filter.casefold():
        return False
    terms = query.casefold().split()
    haystack = " ".join(str(value) for value in (
        switch.hostname, switch.host, switch.model, switch.firmware, *values,
    )).casefold()
    return all(term in haystack for term in terms)

def _link_tag(link: str) -> str:
    """Return the Treeview tag that corresponds to a link state."""
    key = link.lower()
    if key == "up":
        return "up"
    if key == "disabled":
        return "disabled"
    return "down"


def _build_port_mac_index(
    switch: ParsedSwitchData,
) -> dict[str, list[str]]:
    """Index port → MACs for one switch snapshot."""
    port_map: dict[str, list[str]] = {}
    for entry in switch.mac_table:
        port_map.setdefault(entry.port, []).append(entry.mac)
    return port_map
