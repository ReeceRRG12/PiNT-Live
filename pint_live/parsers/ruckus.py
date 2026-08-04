"""Parsers for Ruckus ICX (FastIron OS) CLI output."""

import re
from typing import Optional

from pint_live.models import InterfaceEntry, LagEntry, MacEntry, NeighborEntry, VlanEntry, ParsedSwitchData


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
_PORT_LIST_RE = re.compile(r"(?:e(?:the)?\s+)?(\d+/\d+/\d+)(?:\s+to\s+(\d+/\d+/\d+))?", re.IGNORECASE)
_HOSTNAME_RE  = re.compile(r'^hostname\s+["\']?(.+?)["\']?$', re.IGNORECASE)
_LAG_SHOW_HDR_RE = re.compile(
    r'^===\s+LAG\s+"([^"]+)"\s+ID\s+(\d+)\s+\((\S+)\s+(\S+)\)\s+===',
    re.IGNORECASE,
)
_LAG_CFG_HDR_RE = re.compile(r"^lag\s+(.+?)\s+(dynamic|static)\s+id\s+(\d+)$", re.IGNORECASE)
_LAG_REF_RE = re.compile(r"\blag\s+(\d+)(?:\s+to\s+(\d+))?", re.IGNORECASE)


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


def _expand_lag_list(line: str) -> list[str]:
    """Extract LAG IDs from text such as 'lag 1 to 2 lag 6 lag 9 to 11'."""
    lag_ids = []
    for match in _LAG_REF_RE.finditer(line):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        lag_ids.extend(str(lag_id) for lag_id in range(start, end + 1))
    return lag_ids


def _parse_lag_output(output: str, data: ParsedSwitchData) -> None:
    """Parse operational LAG details from ``show lag``."""
    current: Optional[LagEntry] = None
    reading_member_table = False

    for line in output.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        header = _LAG_SHOW_HDR_RE.match(stripped)
        if header:
            current = LagEntry(
                lag_id=header.group(2),
                name=header.group(1),
                mode=header.group(3).capitalize(),
                deployed=header.group(4).lower() == "deployed",
            )
            data.lags.append(current)
            reading_member_table = False
            continue
        if current is None:
            continue
        if stripped.startswith("Ports:"):
            current.members = _parse_port_list(stripped.split(":", 1)[1])
        elif stripped.startswith("Lag Interface:"):
            current.interface = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Trunk Type:"):
            current.trunk_type = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("LACP Key:"):
            current.lacp_key = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Port") and "Link" in stripped and "State" in stripped:
            reading_member_table = True
        elif stripped.startswith("Port") and "[Sys P]" in stripped:
            reading_member_table = False
        elif reading_member_table:
            member = re.match(r"^(\d+/\d+/\d+)\s+(Up|Down)\b", stripped, re.IGNORECASE)
            if member:
                current.member_states[member.group(1)] = member.group(2).capitalize()


def _parse_lag_config(output: str, data: ParsedSwitchData) -> None:
    """Backfill configured LAG names/members when operational output is absent."""
    lag_map = {lag.lag_id: lag for lag in data.lags}
    current: Optional[LagEntry] = None
    for line in output.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        header = _LAG_CFG_HDR_RE.match(stripped)
        if header:
            lag_id = header.group(3)
            current = lag_map.get(lag_id)
            if current is None:
                current = LagEntry(lag_id=lag_id)
                data.lags.append(current)
                lag_map[lag_id] = current
            current.name = current.name or header.group(1).strip('"')
            current.mode = current.mode or header.group(2).capitalize()
            continue
        if stripped == "!":
            current = None
            continue
        if current is not None and stripped.startswith("ports "):
            members = _parse_port_list(stripped[6:])
            if members:
                current.members = members


def _parse_running_config(output: str, data: ParsedSwitchData) -> None:
    current_vlan: Optional[VlanEntry] = None

    for line in output.splitlines():
        stripped = line.strip()

        # Some FastIron versions omit "System Name" from show version but
        # include the configured hostname in show running-config.
        if not data.hostname:
            hostname_match = _HOSTNAME_RE.match(stripped)
            if hostname_match:
                data.hostname = hostname_match.group(1).strip()

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
            current_vlan.tagged_lags.extend(_expand_lag_list(stripped))
        elif stripped.lower().startswith("untagged"):
            current_vlan.untagged_ports.extend(_parse_port_list(stripped))
            current_vlan.untagged_lags.extend(_expand_lag_list(stripped))


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


def _enrich_lags_with_vlans(data: ParsedSwitchData) -> None:
    lag_map = {lag.lag_id: lag for lag in data.lags}
    tagged: dict[str, list[str]] = {}
    for vlan in data.vlans:
        label = f"{vlan.vlan_id}" + (f" ({vlan.name})" if vlan.name else "")
        for lag_id in vlan.untagged_lags:
            if lag_id in lag_map:
                lag_map[lag_id].untagged_vlan = label
        for lag_id in vlan.tagged_lags:
            if lag_id in lag_map:
                tagged.setdefault(lag_id, []).append(label)
    for lag_id, labels in tagged.items():
        lag_map[lag_id].tagged_vlans = ", ".join(labels)


# ---------------------------------------------------------------------------
# LLDP / CDP neighbours
# ---------------------------------------------------------------------------

_NEIGHBOR_FIELD_RE = re.compile(r"^\s*([^:]+?)\s*:\s*(.*?)\s*$")


def _neighbor_key(label: str) -> Optional[str]:
    """Map FastIron LLDP/CDP labels (which vary by release) to our model."""
    key = re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()
    if key in {"local port", "local interface", "local intf", "port"}:
        return "local_port"
    if key in {"chassis id", "system name", "device id", "device identifier"}:
        return "device_id"
    if key in {
        "port id", "port identifier", "port description", "remote port",
        "remote interface", "interface",
    }:
        return "remote_port"
    if (
        key in {"management address", "management ip", "ip address", "ipv4 address", "address"}
        or key.startswith("management address ipv")
    ):
        return "management_ip"
    if key in {"system description", "platform", "device platform"}:
        return "platform"
    if key in {"system capabilities", "enabled capabilities", "capabilities", "capability"}:
        return "capabilities"
    return None


def _clean_neighbor_ip(value: str) -> str:
    match = re.search(r"(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9.])", value)
    return match.group(0) if match else value.strip()


def _clean_neighbor_value(value: str) -> str:
    """Remove matching CLI quotes without altering punctuation inside values."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_neighbors(output: str, protocol: str, data: ParsedSwitchData) -> None:
    """Parse detail output as field blocks, tolerating FastIron label changes."""
    current: dict[str, str] = {}

    def flush() -> None:
        if not current.get("local_port"):
            current.clear()
            return
        device_id = current.get("device_id", "")
        # Prefer the human-friendly system/device name when both it and a
        # chassis identifier appear in a detail block.
        if current.get("system_name"):
            device_id = current["system_name"]
        data.neighbors.append(NeighborEntry(
            protocol=protocol,
            local_port=current.get("local_port", ""),
            device_id=_clean_neighbor_value(device_id),
            management_ip=_clean_neighbor_ip(current.get("management_ip", "")),
            remote_port=_clean_neighbor_value(current.get("remote_port", "")),
            platform=_clean_neighbor_value(current.get("platform", "")),
            capabilities=_clean_neighbor_value(current.get("capabilities", "")),
        ))
        current.clear()

    for line in output.splitlines():
        match = _NEIGHBOR_FIELD_RE.match(line)
        if not match:
            if current and (not line.strip() or re.match(r"^[-=]{3,}$", line.strip())):
                flush()
            continue
        label, value = match.groups()
        normalised_label = re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()
        key = _neighbor_key(label)
        if key == "local_port" and current.get("local_port"):
            flush()
        if normalised_label == "system name":
            current["system_name"] = value
        elif key and value and value.lower() not in {"not advertised", "none", "n/a"}:
            # Preserve the first useful value except for management address,
            # where an IPv4 value should replace an earlier subtype line.
            if key not in current or key == "management_ip":
                current[key] = value
    flush()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(raw) -> ParsedSwitchData:
    """Parse a RawSwitchData object into structured ParsedSwitchData."""
    data = ParsedSwitchData(host=raw.host)
    _parse_version(raw.version_output, data)
    _parse_interfaces(raw.interfaces_output, data)
    _parse_mac_table(raw.mac_table_output, data)
    _parse_lag_output(getattr(raw, "lag_output", ""), data)
    _parse_lag_config(raw.running_config_output, data)
    _parse_running_config(raw.running_config_output, data)
    _parse_neighbors(getattr(raw, "lldp_neighbors_output", ""), "LLDP", data)
    _parse_neighbors(getattr(raw, "cdp_neighbors_output", ""), "CDP", data)
    _enrich_interfaces_with_vlans(data)
    _enrich_lags_with_vlans(data)
    data.raw_outputs = {
        "show version": raw.version_output,
        "show interfaces brief": raw.interfaces_output,
        "show mac-address": raw.mac_table_output,
        "show lag": getattr(raw, "lag_output", ""),
        "show lldp neighbors detail": getattr(raw, "lldp_neighbors_output", ""),
        "show cdp neighbors detail": getattr(raw, "cdp_neighbors_output", ""),
        "show running-config": raw.running_config_output,
    }
    return data
