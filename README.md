# 🍺 PiNT Live

### Pi Network Tools — Live

> **Automated network documentation. Pull live switch data, map every port to a MAC to an IP, and export clean, accurate spreadsheets — in minutes, not days.**

---

## What is PiNT Live?

Network documentation is painful. It's out of date the moment you write it, and half the time it never gets written at all.

PiNT Live fixes that. Provide it with a list of switch IPs and credentials, point it at your network, and it does the rest — SSHing into each device, pulling live data, and building you a structured, accurate Excel workbook that reflects your network *right now*.

---

## ✨ Features

- **Multi-switch polling** — provide a list of IPs and credentials, PiNT Live connects to each one automatically over SSH (or Telnet, with a warning)
- **Mixed-vendor polling in one run** — each switch can be set to **Ruckus**, **Cisco IOS / IOS-XE**, or **HP/Aruba ProCurve** independently, with the correct command set used for each
- **Per-switch or shared credentials** — use one username/password for the whole site, or override per switch via the **Configure all switches…** modal
- **Resilient site polling** — a failed switch is recorded without breaking the chain; transient read timeouts receive one clean reconnect/retry, and every session is closed reliably
- **Stop control** — cooperatively stop between commands or switches while preserving completed results
- **Live data collection** — collects version/system, interface, MAC-table, running configuration, and Ruckus LAG and LLDP/CDP neighbour information using vendor-appropriate commands
- **Ruckus LAG visibility** — maps LAG names and IDs to physical members, member health, and tagged/untagged VLANs
- **Optional ARP enrichment** — load one or more ARP exports (.xlsx) and PiNT Live maps every port's MAC to its IP and hostname
- **Structured Excel export** — Summary, per-switch, and Ruckus LAG sheets with port-state colour coding, VLANs, MACs, LLDP/CDP neighbour names and management IPs, and optional ARP-resolved IP/Hostname columns
- **Workbook navigation** — Summary links open each switch's Main, RAW, and LAG sheets; every detail sheet links back to Summary
- **Optional raw-output sheets** — include searchable, line-numbered CLI output when needed, with an explicit sensitive-data warning
- **Large-site UI performance** — a lightweight results table handles site-sized polls without creating thousands of individual GUI widgets
- **Scrollable sidebar** — all controls remain reachable when many switches are added
- **Clean, readable output** — built for sharing with teams and clients, not just engineers

---

## Download the desktop app

[**Download PiNT Live v0.7.0 Beta 3**](https://github.com/ReeceRRG12/PiNT-Live/releases/tag/v0.7.0-beta.3) — no Python installation needed.

| Platform | Download | Open the app |
|---|---|---|
| Windows 10/11, x64 | `PiNT-Live-v0.7.0-beta.3-Windows-x64.exe` | Download and double-click the portable EXE. |
| macOS, Apple Silicon (M-series) | `PiNT-Live-v0.7.0-beta.3-macOS-Apple-Silicon.dmg` | Open the DMG, drag **PiNT Live** into **Applications**, then launch it there. |
| macOS, Intel | `PiNT-Live-v0.7.0-beta.3-macOS-Intel.dmg` | Open the DMG, drag **PiNT Live** into **Applications**, then launch it there. |

These beta builds are not publisher-signed or Apple-notarized. Windows SmartScreen or macOS Gatekeeper may ask for approval. On macOS, if launch is blocked, follow [Apple's first-launch guidance](https://support.apple.com/en-gb/102445) only for the download you trust. Each download has a SHA-256 checksum alongside it. Mac builds are checked on macOS 15; older versions are not yet validated. Live switch validation of this beta remains outstanding; v0.6.1 remains stable.

### Getting started

1. Add your switch IPs or hostnames. Use **Edit** to choose a vendor for an individual switch.
2. Open **Credentials & vendors…** to set shared credentials or per-switch overrides.
3. Keep **SSH** selected, optionally load ARP workbooks, and click **Poll switches**.
4. Search or filter the results, then **Export to Excel**. The workbook includes all collected results regardless of the visible filter.

**⌘F / Ctrl+F** focuses search; **⌘E / Ctrl+E** starts export when results are available. Poll and Stop stay visible while the setup panel scrolls.

---

## ▶️ Run from source

PiNT Live requires Python 3.10 or newer. From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
pint-live
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

On later launches, activate the existing environment and run `pint-live` again.

To run the automated checks from the project directory:

```bash
python -m unittest discover -s tests -v
```

The checks use simulated switch data and do not connect to live hardware. Current maintenance work and its verification status are recorded in [PROJECT_STATE.md](PROJECT_STATE.md).

---

## 🗺️ Roadmap

### Next — Automation / Scheduled Logging
- Run polls on a schedule (every N hours / cron) and auto-export to a configured directory
- Headless CLI mode so a server can keep a rolling log of network state for forensics
- Time-series friendly output (CSV/SQLite append) to make diffing across snapshots tractable

### Future — Push/Pull (Desired-State Management)
- Use the exported Excel sheet as a source of truth
- PiNT Live diffs the spreadsheet against live switch state and pushes only the delta
- Dry-run / preview mode before any changes are committed
- Turn your documentation into your deployment tool

---

## 🧰 Tech Stack

| Component | Library |
|---|---|
| SSH / Telnet device comms | [Netmiko](https://github.com/ktbyers/netmiko) |
| Excel I/O (export + ARP load) | [openpyxl](https://openpyxl.readthedocs.io/) |
| Desktop UI | [customtkinter](https://github.com/TomSchimansky/CustomTkinter) |
| Asset / image handling | [Pillow](https://python-pillow.org/) |
| Windows EXE / macOS app build | [PyInstaller](https://pyinstaller.org/) |

---

## 🔒 Security

Credentials are held in application memory for the polling session and are not written to project files or Excel exports. Telnet is supported with an explicit warning, but SSH is strongly recommended.

Optional raw-output worksheets can contain the complete running configuration, including password hashes, SNMP communities, usernames, management addresses, and other sensitive client data. They are disabled by default and should be handled as confidential when enabled.

---

## 📁 Project Structure

```
pint-live/
├── core/           # SSH connections, session management
├── collectors/     # Per-vendor command sets and data collection
├── parsers/        # TextFSM / NAPALM output parsing
├── exporters/      # Excel workbook generation
└── ui/             # Desktop GUI and reusable interface components
```

---

## 🚧 Status

**v0.7.0-beta.3 — Desktop experience beta** — adds a refreshed workspace, searchable results, native display scaling, and Windows/macOS downloads on top of the reliability fixes. These changes are awaiting live hardware validation. **v0.6.1 remains the stable release.** See [RELEASE_NOTES.md](RELEASE_NOTES.md) for the changes and validation details.

---

## 🤝 Contributing

Contributions, ideas, and feedback are welcome — especially from network engineers who've felt this pain firsthand. Open an issue to start a conversation.

---

## 📄 License

[MIT](LICENSE)

---

*Part of the PiNT (Pi Network Tools) project family.*
