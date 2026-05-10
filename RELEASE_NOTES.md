# PiNT Live — Release Notes

---

## v0.1.0 — Initial Release

### Summary
First working release of PiNT Live. SSH into your switches, pull live data, and export a clean, colour-coded Excel workbook in minutes.

---

### Features

#### Multi-vendor support
| Vendor | Status |
|---|---|
| Ruckus ICX (FastIron OS) | ✅ Tested & confirmed working |
| Cisco IOS / IOS-XE | 🔶 Implemented — awaiting hardware testing |
| HP/Aruba ProCurve (ArubaOS-Switch) | 🔶 Implemented — awaiting hardware testing |

#### Data collected per switch
- `show version` — hostname, model, firmware version
- `show interfaces brief` — per-port link state, speed, duplex
- `show mac-address` / `show mac address-table` — MAC to port mapping
- `show running-config` — VLAN names, untagged and tagged VLAN assignments per interface

#### Excel export
- Summary tab — all switches at a glance (total ports, up/down/disabled counts)
- Per-switch tab — every interface with Interface, Link state, Speed, Duplex, Untagged VLAN, Tagged VLANs, MAC(s), Description
- Colour-coded rows — 🟢 Up / 🔴 Down / ⚫ Disabled

#### Desktop GUI
- Dark theme matching PiNT desktop styling
- PiNT Live logo in sidebar and About panel
- SSH / Telnet protocol selection (Telnet shows security warning before connecting)
- Vendor selection buttons (Ruckus / Cisco IOS / HP/Aruba)
- Dynamic switch IP list — add / remove rows
- Shared credentials option for polling multiple switches in one run
- Live progress bar and status messages per switch
- Export to Excel via save dialog
- About panel with version, description, and contact links
- DPI-aware scaling for high-resolution displays

#### Architecture
- Modular codebase — each GUI element in its own file (`theme.py`, `sidebar.py`, `results_table.py`, `about_panel.py`, `scale_manager.py`, `assets.py`)
- Vendor registry (`vendors.py`) — adding a new vendor requires only a new collector + parser, no GUI changes
- Shared data models (`models.py`) — all vendors produce identical structures consumed by the exporter and GUI
- Background threading — UI stays responsive during polling
- Credentials never saved to disk

---

### Known limitations / coming soon
- v2: Push/pull desired-state management (diff spreadsheet against live switch, push delta)
- v3: L2 topology mapping — correlate nmap XML scan results with switch MAC tables (Port → MAC → IP → Hostname)
- Juniper and Cisco NX-OS vendor support planned
- Standalone `.exe` build (PyInstaller) not yet validated end-to-end

---

*Part of the PiNT (Pi Network Tools) project family.*
