"""Parsers for HP/Aruba ProCurve (ArubaOS-Switch / ProVision) CLI output."""

import re
from typing import Optional

from pint_live.models import InterfaceEntry, MacEntry, VlanEntry, ParsedSwitchData


# ---------------------------------------------------------------------------
# System info  (show system)
# ---------------------------------------------------------------------------
#
# System Name        : MySwitch
# Software revision  : WB.16.10.0012
# Chassis            : HP J9727A 2920-48G-PoE+ Switch

def _parse_system(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        if "System Name" in line and ":" in line:
            data.hostname = line.split(":", 1)[1].strip()
        elif "Software revision" in line and ":" in line:
            data.firmware = line.split(":", 1)[1].strip()
        elif "Chassis" in line and ":" in line:
            # e.g. "HP J9727A 2920-48G-PoE+ Switch"
            chassis = line.split(":", 1)[1].strip()
            # Try to pull model number out (e.g. "J9727A 2920-48G-PoE+")
            m = re.search(r"(J\d+\S*\s+\S+)", chassis, re.IGNORECASE)
            data.model = m.group(1) if m else chassis


# ---------------------------------------------------------------------------
# Interfaces  (show interfaces brief)
# ---------------------------------------------------------------------------
#
# HP ProCurve ArubaOS-Switch output:
#
#  Status and Counters - Port Status
#
#   Port    Type       | Intrusion  Enabled  Link    ActMode    SpDpx
#   ------- ---------- + ---------  -------  ------  ---------  ------
#   1       100/1000T  |  No        Yes       Down   1000FDx    1000FDx
#   2       100/1000T  |  No        Yes       Up     1000FDx    1000FDx
#   A1      1000T      |  No        Yes       Up     1000FDx    1000FDx

_INTF_RE = re.compile(
    r"^\s*(?P<port>\S+)\s+"
    r"(?P<type>\S+)\s+\|\s+"
    r"(?P<intrusion>\S+)\s+"
    r"(?P<enabled>\S+)\s+"
    r"(?P<link>Up|Down)\s+"
    r"(?P<actmode>\S+)\s+"
    r"(?P<spdpx>\S+)",
    re.IGNORECASE,
)


def _parse_interfaces(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        m = _INTF_RE.match(line)
        if not m:
            continue
        enabled = m.group("enabled").lower()
        link_raw = m.group("link").capitalize()
        # If admin-disabled, override link state
        link = "Disabled" if enabled == "no" else link_raw
        actmode = m.group("actmode")  # e.g. "1000FDx", "100HDx", "Auto"
        # Split speed and duplex from actmode (e.g. "1000FDx" → speed=1000, duplex=Full)
        speed, duplex = _split_actmode(actmode)
        data.interfaces.append(InterfaceEntry(
            port=m.group("port"),
            link=link,
            state="Connected" if link == "Up" else link,
            duplex=duplex,
            speed=speed,
            tag="",
            pvid="",
            description="",
        ))


def _split_actmode(actmode: str) -> tuple[str, str]:
    """Parse '1000FDx' → ('1G', 'Full'), '100HDx' → ('100M', 'Half'), 'Auto' → ('Auto', 'Auto')."""
    m = re.match(r"(\d+)(FDx|HDx)", actmode, re.IGNORECASE)
    if not m:
        return actmode, ""
    speed_mbps = int(m.group(1))
    duplex = "Full" if m.group(2).upper() == "FDX" else "Half"
    if speed_mbps >= 1000:
        speed = f"{speed_mbps // 1000}G"
    else:
        speed = f"{speed_mbps}M"
    return speed, duplex


# ---------------------------------------------------------------------------
# MAC address table  (show mac-address)
# ---------------------------------------------------------------------------
#
#  Status and Counters - Port Address Table
#
#   MAC Address    Located on Port
#   -------------  ---------------
#   001122-334455  1
#   aabbcc-112233  2
#
# Note: HP uses dashes not dots in MAC, and no VLAN column here.
# VLAN comes from running config cross-reference.

_MAC_RE = re.compile(
    r"^\s*(?P<mac>[0-9a-f]{6}-[0-9a-f]{6})\s+(?P<port>\S+)",
    re.IGNORECASE,
)


def _normalise_mac(mac: str) -> str:
    """Convert HP 'aabbcc-112233' to standard 'AA:BB:CC:11:22:33' dotted format."""
    raw = mac.replace("-", "")
    return ".".join(raw[i:i+4] for i in range(0, 12, 4)).upper()


def _parse_mac_table(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        m = _MAC_RE.match(line)
        if not m:
            continue
        data.mac_table.append(MacEntry(
            mac=_normalise_mac(m.group("mac")),
            port=m.group("port"),
            vlan="",        # HP's basic mac table has no VLAN column
            entry_type="Dynamic",
        ))


# ---------------------------------------------------------------------------
# Running config — VLAN blocks + port assignments
# ---------------------------------------------------------------------------
#
# vlan 1
#    name "DEFAULT_VLAN"
#    untagged 1-24
#    tagged 25-28
#    exit
#
# vlan 10
#    name "USERS"
#    untagged 1-20
#    tagged 25-28
#    exit

_VLAN_HDR_RE  = re.compile(r"^vlan\s+(\d+)", re.IGNORECASE)
_VLAN_NAME_RE = re.compile(r'^\s+name\s+"?([^"]+)"?', re.IGNORECASE)
_UNTAGGED_RE  = re.compile(r"^\s+untagged\s+(.+)", re.IGNORECASE)
_TAGGED_RE    = re.compile(r"^\s+tagged\s+(.+)", re.IGNORECASE)
_PORT_NAME_RE = re.compile(r"^\s+name\s+(\S+)\s+\"(.+)\"", re.IGNORECASE)


def _expand_hp_port_range(range_str: str) -> list[str]:
    """Expand '1-24,26,28' or 'A1-A4' into individual port IDs."""
    ports = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            # Numeric range
            if lo.isdigit() and hi.isdigit():
                ports.extend(str(p) for p in range(int(lo), int(hi) + 1))
            else:
                # Lettered range e.g. A1-A4
                prefix = re.match(r"[A-Za-z]+", lo)
                pref = prefix.group(0) if prefix else ""
                lo_n = int(lo[len(pref):])
                hi_n = int(hi[len(pref):])
                ports.extend(f"{pref}{p}" for p in range(lo_n, hi_n + 1))
        else:
            ports.append(part)
    return ports


def _parse_running_config(output: str, data: ParsedSwitchData) -> None:
    current_vlan: Optional[VlanEntry] = None

    for line in output.splitlines():
        stripped = line.strip()

        vh = _VLAN_HDR_RE.match(stripped)
        if vh:
            current_vlan = VlanEntry(vlan_id=vh.group(1), name="")
            data.vlans.append(current_vlan)
            continue

        if stripped.lower() == "exit":
            current_vlan = None
            continue

        if current_vlan is None:
            continue

        nm = _VLAN_NAME_RE.match(line)
        if nm:
            current_vlan.name = nm.group(1).strip()
            continue

        um = _UNTAGGED_RE.match(line)
        if um:
            current_vlan.untagged_ports.extend(_expand_hp_port_range(um.group(1)))
            continue

        tm = _TAGGED_RE.match(line)
        if tm:
            current_vlan.tagged_ports.extend(_expand_hp_port_range(tm.group(1)))


def _enrich_interfaces(data: ParsedSwitchData) -> None:
    """Enrich interface entries with VLAN info from the parsed VLAN list."""
    port_vlans: dict[str, list[tuple[str, str, bool]]] = {}
    for vlan in data.vlans:
        label = f"{vlan.vlan_id}" + (f" ({vlan.name})" if vlan.name else "")
        for port in vlan.untagged_ports:
            port_vlans.setdefault(port, []).append((vlan.vlan_id, label, False))
        for port in vlan.tagged_ports:
            port_vlans.setdefault(port, []).append((vlan.vlan_id, label, True))

    for intf in data.interfaces:
        entries = port_vlans.get(intf.port, [])
        access = [label for _, label, tagged in entries if not tagged]
        trunk  = [label for _, label, tagged in entries if tagged]
        intf.untagged_vlan = access[0] if access else ""
        intf.tagged_vlans  = ", ".join(trunk)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(raw) -> ParsedSwitchData:
    """Parse an HP/Aruba RawSwitchData into structured ParsedSwitchData."""
    data = ParsedSwitchData(host=raw.host)
    _parse_system(raw.system_output, data)
    _parse_interfaces(raw.interfaces_output, data)
    _parse_mac_table(raw.mac_table_output, data)
    _parse_running_config(raw.running_config_output, data)
    _enrich_interfaces(data)
    data.raw_outputs = {
        "show system": raw.system_output,
        "show interfaces brief": raw.interfaces_output,
        "show mac-address": raw.mac_table_output,
        "show running-config": raw.running_config_output,
    }
    return data
