"""Excel workbook exporter using openpyxl."""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from pint_live.parsers.ruckus import ParsedSwitchData, InterfaceEntry


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COLOUR_UP        = "C6EFCE"   # green fill
COLOUR_DOWN      = "FFC7CE"   # red fill
COLOUR_DISABLED  = "D9D9D9"   # grey fill
COLOUR_HEADER    = "1F4E79"   # dark blue header
COLOUR_HEADER_FG = "FFFFFF"

THIN = Side(style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _header_style(cell, text: str) -> None:
    cell.value = text
    cell.font = Font(bold=True, color=COLOUR_HEADER_FG, size=10)
    cell.fill = PatternFill("solid", fgColor=COLOUR_HEADER)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = BORDER


def _link_fill(link: str) -> PatternFill:
    key = link.lower()
    if key == "up":
        return PatternFill("solid", fgColor=COLOUR_UP)
    if key == "disabled":
        return PatternFill("solid", fgColor=COLOUR_DISABLED)
    return PatternFill("solid", fgColor=COLOUR_DOWN)


def _set_col_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ---------------------------------------------------------------------------
# Per-switch sheet
# ---------------------------------------------------------------------------

_INTF_HEADERS = ["Interface", "Link", "State", "Duplex", "Speed", "Untagged VLAN", "Tagged VLANs", "MAC (from table)", "Description"]
_INTF_WIDTHS  = [14,          10,     12,      10,       10,      20,              32,              22,                  30]
_NUM_COLS     = len(_INTF_HEADERS)


def _write_interfaces_sheet(wb: Workbook, data: ParsedSwitchData) -> None:
    tab_name = (data.hostname or data.host)[:31]  # Excel tab name limit
    ws = wb.create_sheet(title=tab_name)

    # --- Title row ---
    col_span = f"A1:{get_column_letter(_NUM_COLS)}1"
    ws.merge_cells(col_span)
    title_cell = ws["A1"]
    title_cell.value = f"{data.model or 'Ruckus ICX'}  |  {data.hostname or data.host}  |  {data.host}  |  Polled: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    title_cell.font = Font(bold=True, size=11, color=COLOUR_HEADER)
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    ws.append([])  # blank row

    # --- Headers ---
    ws.append(_INTF_HEADERS)
    for col, header in enumerate(_INTF_HEADERS, start=1):
        _header_style(ws.cell(row=3, column=col), header)
    ws.row_dimensions[3].height = 18

    # Build a quick lookup: port -> MACs from mac table
    port_macs: dict[str, list[str]] = {}
    for entry in data.mac_table:
        port_macs.setdefault(entry.port, []).append(entry.mac)

    # --- Data rows ---
    for intf in data.interfaces:
        macs = ", ".join(port_macs.get(intf.port, []))
        row = [
            intf.port,
            intf.link,
            intf.state,
            intf.duplex,
            intf.speed,
            intf.untagged_vlan,
            intf.tagged_vlans,
            macs,
            intf.description,
        ]
        ws.append(row)
        row_idx = ws.max_row
        fill = _link_fill(intf.link)
        for col in range(1, len(row) + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.fill = fill
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center")
            cell.font = Font(size=10)

    _set_col_widths(ws, _INTF_WIDTHS)
    ws.freeze_panes = "A4"


# ---------------------------------------------------------------------------
# Summary sheet
# ---------------------------------------------------------------------------

def _write_summary_sheet(wb: Workbook, all_data: list[ParsedSwitchData]) -> None:
    ws = wb.create_sheet(title="Summary", index=0)

    headers = ["Switch", "Host", "Model", "Firmware", "Total Ports", "Up", "Down", "Disabled"]
    widths  = [20,       18,     24,      16,          12,            8,    8,       10]

    ws.append(headers)
    for col, h in enumerate(headers, start=1):
        _header_style(ws.cell(row=1, column=col), h)
    ws.row_dimensions[1].height = 18

    for data in all_data:
        total    = len(data.interfaces)
        up       = sum(1 for i in data.interfaces if i.link.lower() == "up")
        disabled = sum(1 for i in data.interfaces if i.link.lower() == "disabled")
        down     = total - up - disabled
        ws.append([
            data.hostname or data.host,
            data.host,
            data.model,
            data.firmware,
            total,
            up,
            down,
            disabled,
        ])
        row_idx = ws.max_row
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center")
            cell.font = Font(size=10)

    _set_col_widths(ws, widths)
    ws.freeze_panes = "A2"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def export(all_data: list[ParsedSwitchData], output_path: Path) -> Path:
    """Write all parsed switch data to an Excel workbook and return the path."""
    wb = Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    _write_summary_sheet(wb, all_data)
    for data in all_data:
        _write_interfaces_sheet(wb, data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
