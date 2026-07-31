"""Data collector for Ruckus ICX (FastIron OS) switches."""

from dataclasses import dataclass, field
from typing import Optional

from pint_live.core.polling import PollCancelled


@dataclass
class RawSwitchData:
    host: str
    version_output: str = ""
    interfaces_output: str = ""
    mac_table_output: str = ""
    lag_output: str = ""
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
        "interfaces_output":     "show interfaces brief",
        "mac_table_output":      "show mac-address",
        "lag_output":            "show lag",
        "running_config_output": "show running-config",
    }

    for attr, cmd in commands.items():
        if stop_requested():
            raise PollCancelled()
        # FastIron 09.x can confuse Netmiko's learned prompt after
        # skip-page-display. Timing-based reads avoid waiting for that
        # incorrect prompt; a command completes after three quiet seconds.
        output = connection.send_command_timing(
            cmd,
            last_read=3.0,
            read_timeout=120,
        )
        setattr(data, attr, output)

    return data
