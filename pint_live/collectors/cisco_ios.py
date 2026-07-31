"""Data collector for Cisco IOS / IOS-XE switches."""

from dataclasses import dataclass
from typing import Optional

from pint_live.core.polling import PollCancelled


@dataclass
class RawSwitchData:
    host: str
    version_output: str = ""
    interfaces_output: str = ""
    mac_table_output: str = ""
    running_config_output: str = ""
    error: Optional[str] = None


def collect(connection, host: str, stop_requested=lambda: False) -> RawSwitchData:
    """
    Run collection commands against an open Netmiko session.
    Returns RawSwitchData containing raw CLI output for each command.
    """
    data = RawSwitchData(host=host)

    commands = {
        "version_output":        "show version",
        "interfaces_output":     "show interfaces status",
        "mac_table_output":      "show mac address-table",
        "running_config_output": "show running-config",
    }

    for attr, cmd in commands.items():
        if stop_requested():
            raise PollCancelled()
        output = connection.send_command(cmd, read_timeout=120)
        setattr(data, attr, output)

    return data
