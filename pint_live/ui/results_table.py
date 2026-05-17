"""
PiNT Live — results table widget.

A scrollable grid that displays polled switch data.
Each switch gets a coloured section header, followed by one row
per interface with link-state colour coding.
"""

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


class ResultsTable(ctk.CTkScrollableFrame):
    """
    Scrollable results table.

    Usage:
        table = ResultsTable(parent)
        table.populate(list_of_ParsedSwitchData)
        table.clear()
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.PANEL_BG)
        super().__init__(master, **kwargs)
        self._arp_table: ArpTable | None = None
        self._draw_column_headers()

    # ── Public interface ───────────────────────────────────────────────────

    def set_arp_table(self, arp_table: ArpTable | None) -> None:
        """Set/clear the ARP table used to add IP/Hostname columns. The table
        only refreshes the next time `populate` is called."""
        self._arp_table = arp_table

    def clear(self) -> None:
        """Remove all rows and redraw the column headers."""
        for widget in self.winfo_children():
            widget.destroy()
        self._draw_column_headers()

    def populate(self, all_data: list[ParsedSwitchData]) -> None:
        """Replace the current contents with rows from all_data."""
        self.clear()
        row_idx = 1

        # Pre-build port → MAC lookup for each switch
        port_macs = _build_port_mac_index(all_data)
        arp       = self._arp_table

        for switch in all_data:
            self._draw_switch_header(row_idx, switch)
            row_idx += 1

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

                self._draw_interface_row(row_idx, row_values, intf.link)
                row_idx += 1

    # ── Private drawing helpers ────────────────────────────────────────────

    def _columns(self) -> list[tuple[str, int]]:
        if self._arp_table is None:
            return _COLUMNS_BASE
        return (
            _COLUMNS_BASE[:_MAC_COL_IDX + 1]
            + _COLUMNS_ARP
            + _COLUMNS_BASE[_MAC_COL_IDX + 1:]
        )

    def _draw_column_headers(self) -> None:
        for col, (label, width) in enumerate(self._columns()):
            ctk.CTkLabel(
                self,
                text=label,
                font=theme.font_bold(11),
                width=width,
                anchor="w",
                text_color=theme.TEXT_MUTED,
            ).grid(row=0, column=col, padx=(4, 8), pady=(2, 4), sticky="w")

    def _draw_switch_header(self, row_idx: int, switch: ParsedSwitchData) -> None:
        """Full-width coloured label above each switch's port rows."""
        label = (
            f"  {switch.hostname or switch.host}"
            f"  ({switch.host})"
            f"  —  {switch.model or 'Unknown'}"
            f"  fw {switch.firmware}"
        )
        ctk.CTkLabel(
            self,
            text=label,
            font=theme.font_bold(11),
            text_color=theme.ACCENT,
            anchor="w",
        ).grid(
            row=row_idx, column=0,
            columnspan=len(self._columns()),
            padx=4, pady=(10, 2), sticky="w",
        )

    def _draw_interface_row(self, row_idx: int, values: list[str], link: str) -> None:
        """Draw one interface row with link-state colour coding on the Link cell."""
        text_colour = _link_colour(link)

        for col, (value, (_, width)) in enumerate(zip(values, self._columns())):
            # Only the Link column gets the link-state colour
            colour = text_colour if col == 1 else theme.TEXT_PRIMARY
            ctk.CTkLabel(
                self,
                text=value,
                width=width,
                anchor="w",
                font=theme.font_small(10),
                text_color=colour,
            ).grid(row=row_idx, column=col, padx=(4, 8), pady=1, sticky="w")


# ── Module-level helpers ───────────────────────────────────────────────────

def _link_colour(link: str) -> str:
    """Return the text colour that corresponds to a link state string."""
    key = link.lower()
    if key == "up":
        return theme.LINK_UP
    if key == "disabled":
        return theme.LINK_DISABLED
    return theme.LINK_DOWN


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
