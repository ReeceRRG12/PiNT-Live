# PiNT Live — Release Notes

---

## v0.2.0 — First Public Release

### What is PiNT Live?
PiNT Live automates network switch documentation. Point it at your switches, give it credentials, and it SSHes in, pulls live data, and hands you a clean, accurate Excel workbook — port states, VLAN assignments, MAC addresses, and more — in minutes rather than days.

---

### What's included in v0.2.0

#### Desktop GUI
- Dark theme desktop application matching PiNT family styling
- PiNT Live logo in the sidebar and About panel
- Sidebar layout with configuration form always visible alongside results
- DPI-aware scaling — looks sharp on high-resolution displays
- About panel with version info and links

#### Switch polling
- Add multiple switch IPs in a single run — poll your whole site at once
- **SSH** (recommended) or **Telnet** protocol selection
  - Telnet displays a security warning before connecting — credentials sent in plaintext
- Shared credentials option — enter once, use for all switches

#### Vendor support
| Vendor | Commands collected | Status |
|---|---|---|
| **Ruckus ICX** (FastIron OS) | `show version` · `show interfaces brief` · `show mac-address` · `show running-config` | ✅ Tested & confirmed working |
| **Cisco IOS / IOS-XE** | `show version` · `show interfaces status` · `show mac address-table` · `show running-config` | 🔶 Implemented — awaiting hardware testing |
| **HP/Aruba ProCurve** (ArubaOS-Switch) | `show system` · `show interfaces brief` · `show mac-address` · `show running-config` | 🔶 Implemented — awaiting hardware testing |

#### Data collected per switch
- Hostname, model, and firmware version
- Per-interface: link state (Up / Down / Disabled), speed, duplex
- VLAN assignments from running config — **Untagged VLAN** and **Tagged VLANs** per port, including VLAN names
- MAC address to port mapping

#### Excel export
- **Summary tab** — all polled switches at a glance with port counts
- **Per-switch tab** — every interface with full detail, colour-coded by link state
  - 🟢 Up · 🔴 Down · ⚫ Disabled
- Save dialog with timestamped default filename
- Credentials are never written to the spreadsheet or saved to disk

#### Standalone executable
- Single `PiNT Live.exe` — no Python install required on the target machine
- Built with PyInstaller, bundling all dependencies
- Distribute directly via GitHub Releases

---

### Architecture highlights
- Modular codebase — GUI, backend, and vendor logic fully separated
- Adding a new vendor requires only a new collector + parser; no GUI changes needed
- All vendors produce identical data structures consumed by the exporter and GUI
- Background threading keeps the UI responsive during polling

---

### Known limitations / coming in future releases
- Cisco IOS and HP/Aruba parsers are written to standard output formats — minor regex tweaks may be needed against specific firmware versions once hardware tested
- Juniper and Cisco NX-OS planned for a future release
- **v0.3 planned:** Push/pull desired-state management — diff a spreadsheet against live switch state and push only the delta
- **v0.4 planned:** L2 topology mapping — correlate nmap XML scan results with switch MAC tables (Port → MAC → IP → Hostname)

---

### Installation
Download `PiNT Live.exe` from the release assets and run it. No installer, no Python, no dependencies.

---

*Part of the PiNT (Pi Network Tools) project family.*
*Built by Reece Rainer — [reece@pinetworktools.com](mailto:reece@pinetworktools.com)*
