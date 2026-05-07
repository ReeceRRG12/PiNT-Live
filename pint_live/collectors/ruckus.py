"""Data collector for Ruckus ICX (FastIron OS) switches."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawSwitchData:
    host: str
    version_output: str = ""
    interfaces_output: str = ""
    mac_table_output: str = ""
    running_config_output: str = ""
    error: Optional[str] = None


def collect(connection, host: str) -> RawSwitchData:
    """
    Run collection commands against an open Netmiko session.
    Returns RawSwitchData containing raw CLI output for each command.
    """
    data = RawSwitchData(host=host)

    commands = {
        "version_output":        "show version",
        "interfaces_output":     "show interfaces brief",
        "mac_table_output":      "show mac-address",
        "running_config_output": "show running-config",
    }

    for attr, cmd in commands.items():
        output = connection.send_command(cmd, read_timeout=120)
        setattr(data, attr, output)

    return data
