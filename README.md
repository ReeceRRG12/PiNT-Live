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
- **Live data collection** — pulls `show version`, `show interface brief`, `show mac address-table`, and `show running-config`
- **Optional ARP enrichment** — load one or more ARP exports (.xlsx) and PiNT Live maps every port's MAC to its IP and hostname
- **Structured Excel export** — per-switch tabs, port state colour coding (🟢 up / 🔴 down / ⚫ admin down), VLANs (untagged + tagged), MACs, and ARP-resolved IP/Hostname columns when available
- **Clean, readable output** — built for sharing with teams and clients, not just engineers

---

## 🗺️ Roadmap

### v0.5 — Automation / Scheduled Logging
- Run polls on a schedule (every N hours / cron) and auto-export to a configured directory
- Headless CLI mode so a server can keep a rolling log of network state for forensics
- Time-series friendly output (CSV/SQLite append) to make diffing across snapshots tractable

### Beyond v0.5 — Push/Pull (Desired-State Management)
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
| Standalone exe build | [PyInstaller](https://pyinstaller.org/) |

---

## 🔒 Security

Credential security is a first-class concern in PiNT Live. Passwords are never stored in plaintext config files or spreadsheets. The project will use OS-level secure storage (`keyring`) or encrypted credential vaults, with environment variable support for CI/automated use cases.

---

## 📁 Project Structure

```
pint-live/
├── core/           # SSH connections, session management
├── collectors/     # Per-vendor command sets and data collection
├── parsers/        # TextFSM / NAPALM output parsing
├── exporters/      # Excel, CSV, and future format support
├── ui/             # Interface (CLI initially, GUI planned)
└── docs/           # Documentation and usage guides
```

---

## 🚧 Status

**v0.4.0** — multi-vendor polling shipped. Ruckus is hardware-tested; Cisco IOS and HP/Aruba parsers are implemented and awaiting validation against real gear. See [RELEASE_NOTES.md](RELEASE_NOTES.md) for full change history.

---

## 🤝 Contributing

Contributions, ideas, and feedback are welcome — especially from network engineers who've felt this pain firsthand. Open an issue to start a conversation.

---

## 📄 License

[MIT](LICENSE)

---

*Part of the PiNT (Pi Network Tools) project family.*
