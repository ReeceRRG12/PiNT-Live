"""Data collector for HP/Aruba ProCurve (ArubaOS-Switch / ProVision) switches."""

from dataclasses import dataclass
from typing import Optional

from pint_live.core.polling import PollCancelled


@dataclass
class RawSwitchData:
    host: str
    system_output: str = ""
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
        "system_output":         "show system",
        "interfaces_output":     "show interfaces brief",
        "mac_table_output":      "show mac-address",
        "running_config_output": "show running-config",
    }

    for attr, cmd in commands.items():
        if stop_requested():
            raise PollCancelled()
        output = connection.send_command(cmd, read_timeout=120)
        setattr(data, attr, output)

    return data
