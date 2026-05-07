# 🍺 PiNT Live
### Pi Network Tools — Live

> **Automated network documentation. Pull live switch data, map every port to a MAC to an IP, and export clean, accurate spreadsheets — in minutes, not days.**

---

## What is PiNT Live?

Network documentation is painful. It's out of date the moment you write it, and half the time it never gets written at all.

PiNT Live fixes that. Provide it with a list of switch IPs and credentials, point it at your network, and it does the rest — SSHing into each device, pulling live data, and building you a structured, accurate Excel workbook that reflects your network *right now*.

---

## ✨ Features (v1 — Planned)

- **Multi-switch SSH polling** — provide a list of IPs and credentials, PiNT Live connects to each one automatically
- **Vendor-aware command sets** — select your switch make (Cisco IOS, Cisco NX-OS, HP/Aruba, Juniper, etc.) and PiNT Live uses the correct syntax automatically
- **Live data collection** — pulls `show running-config`, `show interface brief`, `show mac address-table`, and more
- **Structured Excel export** — per-switch tabs, port state colour coding (🟢 up / 🔴 down / ⚫ admin down), port names, MAC addresses, and timestamps
- **Clean, readable output** — built for sharing with teams and clients, not just engineers

---

## 🗺️ Roadmap

### v2 — Push/Pull (Desired-State Management)
- Use the exported Excel sheet as a source of truth
- PiNT Live diffs the spreadsheet against live switch state and pushes only the delta
- Dry-run / preview mode before any changes are committed
- Turn your documentation into your deployment tool

### v3 — L2 Network Mapping
- Upload nmap scan files (XML output) and PiNT Live correlates IPs against MACs
- Every switch port gets: **Port → MAC → IP → Hostname**
- Full L2 topology view without needing active scanning permissions
- Fills the last gap in your documentation — no more unknown endpoints

---

## 🧰 Tech Stack (Planned)

| Component | Library |
|---|---|
| SSH / Device comms | [Netmiko](https://github.com/ktbyers/netmiko) |
| CLI output parsing | [TextFSM](https://github.com/google/textfsm) + [NTC Templates](https://github.com/networktocode/ntc-templates) |
| Cross-vendor abstraction | [NAPALM](https://napalm.readthedocs.io/) |
| Excel generation | [openpyxl](https://openpyxl.readthedocs.io/) |
| Credential handling | `keyring` / encrypted vault |

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

**This project is in early planning / pre-development.**
The repository is a placeholder while the architecture and v1 scope are defined.

Watch this repo or check back for updates as development begins.

---

## 🤝 Contributing

Contributions, ideas, and feedback are welcome — especially from network engineers who've felt this pain firsthand. Open an issue to start a conversation.

---

## 📄 License

TBD

---

*Part of the PiNT (Pi Network Tools) project family.*
