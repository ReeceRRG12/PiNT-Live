# PiNT Live — Release Notes

---

## v0.5.0 — Reliability, LAG Discovery, and Navigable Exports

Released 31 July 2026.

This release hardens multi-switch polling for real client-site use, adds Ruckus LAG visibility, scales the desktop results view to larger sites, and turns the Excel workbook into a linked navigation hub.

### Reliable polling
- A failure on one switch no longer terminates the entire polling thread or leaves the interface permanently busy
- Transient Netmiko read timeouts receive one retry using a fresh connection
- SSH sessions are closed in all success and failure paths
- Unexpected command and parser errors are reported per switch while remaining switches continue
- Empty/unrecognised interface output is treated as an error instead of a blank success
- New **Stop** button cooperatively stops between commands or switches and preserves completed results

### FastIron 09.x compatibility
- Ruckus commands use timing-based reads to avoid prompt-detection failures observed on FastIron `09.0.10h` after `skip-page-display`
- Ruckus hostname parsing falls back to `hostname ...` in the running configuration when `show version` omits `System Name`

### Ruckus LAG discovery
- Collects `show lag` in addition to the existing Ruckus command set
- Parses LAG ID, name, mode, deployment state, interface, trunk type, LACP key, physical members, and member link health
- Resolves `tagged lag` / `untagged lag` configuration, including ranges such as `lag 6 to 17`
- Adds a dedicated LAG worksheet per Ruckus switch with member and VLAN details

### Excel improvements
- Summary rows now link to each switch's **Main**, **RAW**, and **LAG** worksheets
- Every detail worksheet includes a **Back to Summary** link in cell A1
- Optional raw CLI worksheets provide command names, line numbers, and one output line per row
- Raw output remains disabled by default and displays a sensitive-data warning when enabled
- Raw text is forced to Excel string cells to prevent device output beginning with `=` from becoming a formula

### Desktop UI improvements
- Replaced the cell-per-widget results grid with one lightweight native table, eliminating long post-poll hangs on larger sites
- Added horizontal and vertical results scrolling with expandable switch groups
- Made the complete left sidebar scrollable so Poll, Stop, and export options remain reachable with long switch lists

### Validation
- Ruckus and HP/Aruba polling validated against lab hardware, including mixed-vendor polling over a VPN
- Ruckus FastIron `09.0.10h` and `10.0.10g` behaviours exercised during development
- Automated coverage added for timeout retry, error isolation, cleanup, cancellation, parser validation, Ruckus hostname/LAG parsing, raw export safety, and Excel navigation links

### Known limitations
- Stop waits for the active Netmiko command to return or time out; it does not forcibly terminate a socket from the GUI thread
- Cisco IOS / IOS-XE parsing remains awaiting validation against real hardware
- Raw-output workbooks may contain sensitive client configuration and must be protected accordingly

---

## v0.4.0 — Multi-Vendor Polling

Each switch in your polling list can now be set to its own vendor, so you can poll a mixed Ruckus / Cisco / HP-Aruba site in a single run. Credentials can be shared across the whole site (the common case) or overridden per switch.

### What's new in v0.4.0

#### Per-switch vendor selection
- Every switch row in the sidebar now has its own **⚙ cog button**
- Clicking the cog opens a per-switch popup where you pick the vendor (Ruckus / Cisco IOS / HP-Aruba) and — if you've turned shared credentials off — set per-switch username/password overrides
- The status line during polling now shows which vendor is being talked to: `Connecting to 192.168.1.1 (Ruckus)…`

#### Bulk configuration modal
- New **Configure all switches…** button below the IP list opens a modal with:
  - **Shared credentials** at the top — used by every switch unless overridden
  - A **per-switch table** with IP / Vendor / Username / Password columns
  - **Use same credentials for all switches** checkbox — when checked, per-row cred fields are greyed out
- Designed for the two common cases: (a) one cred set, mixed vendors, and (b) different creds per switch

#### Duplicate-IP guard
- If the same IP/host appears more than once in the list, the poll now flags it with a Yes/No warning before running. Avoids accidental double-polling and duplicate sheets in the export.
- Case-insensitive comparison, defaults to **No** so an accidental Enter doesn't push through.

#### Sidebar layout cleanup
- The old global Vendor and Username/Password sections are gone — that state now lives on the bulk modal (shared) or each row (per-switch)
- Sidebar is noticeably less busy as a result

### Behaviour preserved from v0.3.x
- Optional **ARP list (.xlsx)** loading and per-port IP/Hostname enrichment in the Excel export — unchanged
- Excel export Summary tab and per-switch colour-coded tabs — unchanged
- Protocol toggle (SSH / Telnet with security warning) — unchanged

### Architecture notes
- `_SwitchRow` now owns its own `vendor` / `username` / `password` state
- The sidebar emits a per-switch job list — `{host, vendor, username, password}` — instead of one shared vendor for all hosts
- `_start_poll` resolves device_type / collector / parser per switch, so the worker thread is vendor-agnostic
- `theme.font_symbol()` helper added — uses **Segoe UI Symbol** so the ⚙ glyph renders as an actual gear on Windows

### Known limitations
- Cisco IOS and HP/Aruba parsers are still awaiting validation against real gear
- Scheduled / unattended polling is on the v0.5 roadmap (see README)

---

## v0.3.0-rc2 — Multi-file ARP Loading (Pre-release · Hardware Testing Pending)

> ⚠️ **Pre-release.** Rolls up rc1 and adds multi-file ARP support. Hardware testing against a real switch is still pending — `v0.2.0` remains the recommended stable build.

### What's new since rc1

#### Load multiple ARP lists at once
- The file picker now supports **multi-select** — hold Ctrl/Shift to pick one ARP file per VLAN/subnet in a single click
- Each subsequent **Load ARP List(s)…** click is **additive** — appends to the loaded set instead of replacing it. Hit **Clear** to start over.
- Sidebar status switches between single-file (`arp_vlan10.xlsx — 12 entries`) and multi-file (`4 files — 187 entries`) summaries automatically
- Designed for the PiNT Desktop workflow: pull one ARP export per VLAN, then drop them all into PiNT Live

#### Smart merge across ARP sources
- Duplicate MACs across files are deduplicated automatically (last-write-wins on IP)
- **Hostnames are preserved** — a blank hostname in a later file will never overwrite a populated one from an earlier file. Useful when ARP sources vary (DHCP server vs. router ARP cache)
- One bad file no longer kills the whole load — failures are reported per-file and the rest continue to load

#### Updated export prompt
- When ARP data is already loaded, the export dialog now offers **"load more first"** instead of the previous "swap" — matching the new additive model

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
