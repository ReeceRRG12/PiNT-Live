"""Parsers for Ruckus ICX (FastIron OS) CLI output."""

import re
from typing import Optional

from pint_live.models import InterfaceEntry, MacEntry, VlanEntry, ParsedSwitchData


# ---------------------------------------------------------------------------
# Version / hostname
# ---------------------------------------------------------------------------

def _parse_version(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        if "System Name:" in line:
            data.hostname = line.split(":", 1)[1].strip()
        elif "HW: Ruckus" in line or "HW: ICX" in line:
            m = re.search(r"HW:\s+(.+)", line)
            if m:
                data.model = m.group(1).strip()
        elif "SW: Version" in line:
            m = re.search(r"Version\s+(\S+)", line)
            if m:
                data.firmware = m.group(1)


# ---------------------------------------------------------------------------
# Interfaces  (show interfaces brief)
# ---------------------------------------------------------------------------
#
# Port    Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
# 1/1/1   Up      Forward Full 1G    None  No  1    0   cc4e.24ab.cdef
# 1/1/48  Up      Forward Full 1G    1     No  1    0   cc4e.24ab.cdef uplink-sw2

_INTF_RE = re.compile(
    r"^(?P<port>\d+/\d+/\d+)\s+"
    r"(?P<link>\S+)\s+"
    r"(?P<state>\S+)\s+"
    r"(?P<duplex>\S+)\s+"
    r"(?P<speed>\S+)\s+"
    r"(?P<trunk>\S+)\s+"
    r"(?P<tag>\S+)\s+"
    r"(?P<pvid>\S+)\s+"
    r"(?P<pri>\S+)\s+"
    r"(?P<mac>\S+)"
    r"(?:\s+(?P<name>.+))?$",
    re.IGNORECASE,
)


def _parse_interfaces(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        m = _INTF_RE.match(line.strip())
        if not m:
            continue
        data.interfaces.append(InterfaceEntry(
            port=m.group("port"),
            link=m.group("link").capitalize(),
            state=m.group("state").capitalize(),
            duplex=m.group("duplex"),
            speed=m.group("speed"),
            tag=m.group("tag"),
            pvid=m.group("pvid"),
            description=(m.group("name") or "").strip(),
        ))


# ---------------------------------------------------------------------------
# MAC address table  (show mac-address)
# ---------------------------------------------------------------------------
#
# MAC-Address     Port  Type    Vlan
# cc4e.24ab.cdef  1/1/1 Dynamic 1
# 0011.2233.4455  1/1/2 Static  100

_MAC_RE = re.compile(
    r"^(?P<mac>[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+"
    r"(?P<port>\S+)\s+"
    r"(?P<type>\S+)\s+"
    r"(?P<vlan>\d+)",
    re.IGNORECASE,
)


def _parse_mac_table(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        m = _MAC_RE.match(line.strip())
        if not m:
            continue
        data.mac_table.append(MacEntry(
            mac=m.group("mac").upper(),
            port=m.group("port"),
            vlan=m.group("vlan"),
            entry_type=m.group("type").capitalize(),
        ))


# ---------------------------------------------------------------------------
# Running config — VLAN blocks
# ---------------------------------------------------------------------------
#
# Ruckus running config VLAN block format:
#
# vlan 10 name USERS by port
#  tagged ethe 1/1/48
#  untagged ethe 1/1/1 to 1/1/24
# !
# vlan 20 name SERVERS by port
#  tagged ethe 1/1/48
#  untagged ethe 1/1/25 to 1/1/47
# !

_VLAN_HDR_RE  = re.compile(r"^vlan\s+(\d+)(?:\s+name\s+(\S+))?", re.IGNORECASE)
_PORT_LIST_RE = re.compile(r"(?:ethe\s+)?(\d+/\d+/\d+)(?:\s+to\s+(\d+/\d+/\d+))?", re.IGNORECASE)


def _expand_port_range(start: str, end: Optional[str]) -> list[str]:
    """Expand 'slot/mod/start to slot/mod/end' into individual port IDs."""
    if end is None:
        return [start]
    s_parts = start.split("/")
    e_parts = end.split("/")
    # Only expand if slot and module match
    if s_parts[:2] != e_parts[:2]:
        return [start, end]
    prefix = "/".join(s_parts[:2])
    return [f"{prefix}/{p}" for p in range(int(s_parts[2]), int(e_parts[2]) + 1)]


def _parse_port_list(line: str) -> list[str]:
    """Extract all port IDs from a tagged/untagged line, expanding ranges."""
    ports = []
    for m in _PORT_LIST_RE.finditer(line):
        ports.extend(_expand_port_range(m.group(1), m.group(2)))
    return ports


def _parse_running_config(output: str, data: ParsedSwitchData) -> None:
    current_vlan: Optional[VlanEntry] = None

    for line in output.splitlines():
        stripped = line.strip()

        vlan_match = _VLAN_HDR_RE.match(stripped)
        if vlan_match:
            current_vlan = VlanEntry(
                vlan_id=vlan_match.group(1),
                name=vlan_match.group(2) or "",
            )
            data.vlans.append(current_vlan)
            continue

        if stripped == "!" or (stripped and not line.startswith(" ")):
            # End of a block or start of a non-vlan stanza
            if stripped != "!" and current_vlan is not None:
                current_vlan = None
            elif stripped == "!":
                current_vlan = None
            continue

        if current_vlan is None:
            continue

        if stripped.lower().startswith("tagged"):
            current_vlan.tagged_ports.extend(_parse_port_list(stripped))
        elif stripped.lower().startswith("untagged"):
            current_vlan.untagged_ports.extend(_parse_port_list(stripped))


def _enrich_interfaces_with_vlans(data: ParsedSwitchData) -> None:
    """Cross-reference parsed VLANs against interfaces to set access/trunk fields."""

    # Build lookup: port -> list of (vlan_id, name, is_tagged)
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
    """Parse a RawSwitchData object into structured ParsedSwitchData."""
    data = ParsedSwitchData(host=raw.host)
    _parse_version(raw.version_output, data)
    _parse_interfaces(raw.interfaces_output, data)
    _parse_mac_table(raw.mac_table_output, data)
    _parse_running_config(raw.running_config_output, data)
    _enrich_interfaces_with_vlans(data)
    return data
