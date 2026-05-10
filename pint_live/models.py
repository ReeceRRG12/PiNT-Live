"""Shared data models used across all vendor collectors and parsers."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InterfaceEntry:
    port: str
    link: str           # Up / Down / Disabled
    state: str          # Forward / Blocking / Connected / NotConnect / etc.
    duplex: str
    speed: str
    tag: str            # Tagged / Untagged / No
    pvid: str           # Raw PVID from interface table (fallback)
    description: str = ""
    untagged_vlan: str = ""   # e.g. "10 (USERS)"
    tagged_vlans: str = ""    # e.g. "1 (DEFAULT), 20 (MGMT)"


@dataclass
class MacEntry:
    mac: str
    port: str
    vlan: str
    entry_type: str     # Dynamic / Static


@dataclass
class VlanEntry:
    vlan_id: str
    name: str
    tagged_ports: list[str] = field(default_factory=list)
    untagged_ports: list[str] = field(default_factory=list)


@dataclass
class ParsedSwitchData:
    host: str
    hostname: str = ""
    model: str = ""
    firmware: str = ""
    interfaces: list[InterfaceEntry] = field(default_factory=list)
    mac_table: list[MacEntry] = field(default_factory=list)
    vlans: list[VlanEntry] = field(default_factory=list)
