# PiNT Live — Release Notes

---

## v0.3.0-rc1 — ARP Resolution (Pre-release · Hardware Testing Pending)

> ⚠️ **Pre-release.** This build adds the ARP-resolution feature on top of v0.2.0. It has been unit-smoke-tested but **not yet validated against a real switch in a lab**. Use for testing only — `v0.2.0` remains the recommended stable build.

### What's new in v0.3.0-rc1

#### ARP list → Port → IP → Hostname
- Load an ARP table from an Excel workbook (`.xlsx`) and PiNT Live will map every MAC seen on a switch port to its IP and (where available) its hostname
- Flexible header detection — columns named `IP` / `IP Address`, `MAC` / `MAC Address`, and `Hostname` / `Host` / `Name` are all recognised (case-insensitive)
- MAC normalisation handles every common format — colon (`AA:BB:CC:DD:EE:FF`), dotted (`AABB.CCDD.EEFF`), and dash (`AA-BB-CC-DD-EE-FF`) — so switch-table MACs and ARP-list MACs always compare equal
- Ports with multiple MACs (uplinks, trunks) show comma-separated IPs and hostnames in MAC order; unmatched entries leave their slot blank so positions stay aligned

#### Sidebar
- New **ARP List (optional)** section with **Load ARP List…** and **Clear** buttons
- Status line shows the loaded file name and entry count
- On-screen results table refreshes immediately to show the new **IP (ARP)** and **Hostname (ARP)** columns when a list is loaded

#### Export flow
- When you click **Export to Excel**:
  - If an ARP list is loaded → choose to use it, swap to a different file, or skip the ARP columns entirely
  - If none is loaded → choose to load one now or skip
- Each per-switch tab gains **IP (from ARP)** and **Hostname (from ARP)** columns inserted directly after the MAC column — colour-coding and the Summary tab are unchanged

---

### Architecture notes
- New `pint_live/arp.py` module — single responsibility, no UI dependencies, easily unit-testable
- `ArpTable` exposes `lookup` / `resolve_ips` / `resolve_hostnames` so any future exporter or UI panel can re-use the same logic
- Excel exporter and on-screen results table both take an optional `arp_table` parameter — when `None`, output is identical to v0.2.0
- Zero new runtime dependencies — uses `openpyxl`, already bundled

---

### Known limitations
- Hardware testing against Ruckus / Cisco IOS / HP Aruba switches has not yet been completed for this build — please report any column-misalignment or matching issues
- Only `.xlsx` ARP files are supported in this release; CSV / TSV input may be added in a follow-up if useful
- The ARP list is held in memory only — it is not persisted between app launches

---

### Installation
Download `PiNT Live.exe` from the pre-release assets and run it. No installer, no Python, no dependencies. Windows SmartScreen may flag the unsigned binary — click *More info → Run anyway*.

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
