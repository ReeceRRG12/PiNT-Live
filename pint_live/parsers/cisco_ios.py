"""Parsers for Cisco IOS / IOS-XE CLI output."""

import re
from typing import Optional

from pint_live.models import InterfaceEntry, MacEntry, VlanEntry, ParsedSwitchData


# ---------------------------------------------------------------------------
# Version / hostname
# ---------------------------------------------------------------------------
#
# show version output includes:
#   hostname uptime is 2 weeks ...
#   Cisco IOS Software ... Version 15.2(7)E4 ...
#   cisco WS-C2960X-48FPS-L (PowerPC) ...

def _parse_version(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        # First non-blank line is typically: "<hostname> uptime is ..."
        if not data.hostname and "uptime is" in line.lower():
            data.hostname = line.split()[0].strip()
        if not data.model and re.match(r"^cisco\s+\S+", line, re.IGNORECASE):
            m = re.match(r"^cisco\s+(\S+)", line, re.IGNORECASE)
            if m:
                data.model = m.group(1)
        if not data.firmware:
            m = re.search(r"Version\s+([\w().]+)", line)
            if m:
                data.firmware = m.group(1)


# ---------------------------------------------------------------------------
# Interfaces  (show interfaces status)
# ---------------------------------------------------------------------------
#
# Port      Name               Status       Vlan       Duplex  Speed Type
# Gi1/0/1   UPLINK-SW2         connected    trunk        full   1000 10/100/1000BaseTX
# Gi1/0/2                      notconnect   1            auto   auto 10/100/1000BaseTX
# Gi1/0/3   SERVER             connected    20           full    100 10/100/1000BaseTX
# Te1/0/1                      connected    trunk        full  10000 SFP-10GBase-SR

_INTF_RE = re.compile(
    r"^(?P<port>\S+)\s+"
    r"(?P<name>.*?)\s{2,}"
    r"(?P<status>connected|notconnect|disabled|err-disabled|inactive)\s+"
    r"(?P<vlan>\S+)\s+"
    r"(?P<duplex>\S+)\s+"
    r"(?P<speed>\S+)",
    re.IGNORECASE,
)

_STATUS_MAP = {
    "connected":   "Up",
    "notconnect":  "Down",
    "disabled":    "Disabled",
    "err-disabled": "Disabled",
    "inactive":    "Down",
}


def _parse_interfaces(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        m = _INTF_RE.match(line.strip())
        if not m:
            continue
        status = m.group("status").lower()
        link = _STATUS_MAP.get(status, status.capitalize())
        vlan = m.group("vlan")  # may be a number or "trunk"
        data.interfaces.append(InterfaceEntry(
            port=m.group("port"),
            link=link,
            state="Connected" if link == "Up" else link,
            duplex=m.group("duplex").capitalize(),
            speed=m.group("speed"),
            tag="Yes" if vlan.lower() == "trunk" else "No",
            pvid="" if vlan.lower() == "trunk" else vlan,
            description=m.group("name").strip(),
        ))


# ---------------------------------------------------------------------------
# MAC address table  (show mac address-table)
# ---------------------------------------------------------------------------
#
# Vlan    Mac Address       Type        Ports
# ----    -----------       --------    -----
#    1    0011.2233.4455    DYNAMIC     Gi1/0/1
#   20    aabb.cc11.2233    DYNAMIC     Gi1/0/3

_MAC_RE = re.compile(
    r"^\s*(?P<vlan>\d+)\s+"
    r"(?P<mac>[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+"
    r"(?P<type>\S+)\s+"
    r"(?P<port>\S+)",
    re.IGNORECASE,
)


def _parse_mac_table(output: str, data: ParsedSwitchData) -> None:
    for line in output.splitlines():
        m = _MAC_RE.match(line)
        if not m:
            continue
        data.mac_table.append(MacEntry(
            mac=m.group("mac").upper(),
            port=m.group("port"),
            vlan=m.group("vlan"),
            entry_type=m.group("type").capitalize(),
        ))


# ---------------------------------------------------------------------------
# Running config — VLAN names + interface VLAN assignments
# ---------------------------------------------------------------------------
#
# vlan 10
#  name USERS
# !
# interface GigabitEthernet1/0/1
#  description UPLINK
#  switchport trunk native vlan 1
#  switchport trunk allowed vlan 1,10,20
#  switchport mode trunk
# !
# interface GigabitEthernet1/0/3
#  description SERVER
#  switchport access vlan 20
#  switchport mode access
# !

_VLAN_ID_RE   = re.compile(r"^vlan\s+(\d+)$", re.IGNORECASE)
_VLAN_NAME_RE = re.compile(r"^\s+name\s+(.+)$", re.IGNORECASE)
_INTF_HDR_RE  = re.compile(r"^interface\s+(\S+)", re.IGNORECASE)
_ACCESS_RE    = re.compile(r"switchport\s+access\s+vlan\s+(\d+)", re.IGNORECASE)
_NATIVE_RE    = re.compile(r"switchport\s+trunk\s+native\s+vlan\s+(\d+)", re.IGNORECASE)
_ALLOWED_RE   = re.compile(r"switchport\s+trunk\s+allowed\s+vlan\s+(.+)", re.IGNORECASE)
_DESC_RE      = re.compile(r"^\s+description\s+(.+)$", re.IGNORECASE)


def _expand_cisco_vlan_list(vlan_str: str) -> list[str]:
    """Expand '1,10,20-25,30' into individual VLAN IDs."""
    result = []
    for part in vlan_str.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            result.extend(str(v) for v in range(int(lo), int(hi) + 1))
        elif part:
            result.append(part)
    return result


def _normalize_port(name: str) -> str:
    """Abbreviate interface name to match show interfaces status output (e.g. Gi1/0/1)."""
    abbrevs = [
        ("GigabitEthernet", "Gi"),
        ("TenGigabitEthernet", "Te"),
        ("FastEthernet", "Fa"),
        ("TwentyFiveGigE", "Twe"),
        ("FortyGigabitEthernet", "Fo"),
        ("HundredGigE", "Hu"),
    ]
    for full, short in abbrevs:
        if name.lower().startswith(full.lower()):
            return short + name[len(full):]
    return name


def _parse_running_config(output: str, data: ParsedSwitchData) -> None:
    vlan_map: dict[str, VlanEntry] = {}
    # First pass: collect VLAN names
    current_vlan_id: Optional[str] = None
    for line in output.splitlines():
        stripped = line.strip()
        vm = _VLAN_ID_RE.match(stripped)
        if vm:
            current_vlan_id = vm.group(1)
            vlan_map[current_vlan_id] = VlanEntry(vlan_id=current_vlan_id, name="")
            continue
        if stripped == "!" or (stripped and not line.startswith(" ")):
            current_vlan_id = None
            continue
        if current_vlan_id:
            nm = _VLAN_NAME_RE.match(line)
            if nm:
                vlan_map[current_vlan_id].name = nm.group(1).strip()

    data.vlans = list(vlan_map.values())

    # Second pass: collect per-interface VLAN assignments and descriptions
    # Build lookup: normalised port name -> {access_vlan, native_vlan, allowed_vlans, description}
    intf_config: dict[str, dict] = {}
    current_intf: Optional[str] = None
    for line in output.splitlines():
        stripped = line.strip()
        im = _INTF_HDR_RE.match(stripped)
        if im:
            current_intf = _normalize_port(im.group(1))
            intf_config[current_intf] = {}
            continue
        if stripped == "!" or (stripped and not line.startswith(" ")):
            current_intf = None
            continue
        if current_intf is None:
            continue
        am = _ACCESS_RE.search(stripped)
        if am:
            intf_config[current_intf]["access"] = am.group(1)
        nm = _NATIVE_RE.search(stripped)
        if nm:
            intf_config[current_intf]["native"] = nm.group(1)
        alm = _ALLOWED_RE.search(stripped)
        if alm:
            intf_config[current_intf]["allowed"] = _expand_cisco_vlan_list(alm.group(1))
        dm = _DESC_RE.match(line)
        if dm:
            intf_config[current_intf]["description"] = dm.group(1).strip()

    # Enrich interfaces
    def vlan_label(vid: str) -> str:
        entry = vlan_map.get(vid)
        return f"{vid} ({entry.name})" if entry and entry.name else vid

    for intf in data.interfaces:
        cfg = intf_config.get(intf.port, {})
        # Backfill description from running config if not already set
        if not intf.description and cfg.get("description"):
            intf.description = cfg["description"]
        if "access" in cfg:
            intf.untagged_vlan = vlan_label(cfg["access"])
        elif "native" in cfg:
            intf.untagged_vlan = vlan_label(cfg["native"])
        if "allowed" in cfg:
            intf.tagged_vlans = ", ".join(vlan_label(v) for v in cfg["allowed"])


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(raw) -> ParsedSwitchData:
    """Parse a Cisco IOS RawSwitchData into structured ParsedSwitchData."""
    data = ParsedSwitchData(host=raw.host)
    _parse_version(raw.version_output, data)
    _parse_interfaces(raw.interfaces_output, data)
    _parse_mac_table(raw.mac_table_output, data)
    _parse_running_config(raw.running_config_output, data)
    data.raw_outputs = {
        "show version": raw.version_output,
        "show interfaces status": raw.interfaces_output,
        "show mac address-table": raw.mac_table_output,
        "show running-config": raw.running_config_output,
    }
    return data
