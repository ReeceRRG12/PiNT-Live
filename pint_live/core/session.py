"""SSH session management via Netmiko."""

from dataclasses import dataclass
from typing import Optional

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
from rich.console import Console

console = Console()


@dataclass
class Credentials:
    username: str
    password: str


@dataclass
class SwitchTarget:
    host: str
    credentials: Credentials
    port: int = 22


class SessionError(Exception):
    pass


def open_session(target: SwitchTarget, device_type: str = "ruckus_fastiron"):
    """Open a Netmiko SSH session to a switch. Caller is responsible for disconnecting."""
    try:
        connection = ConnectHandler(
            device_type=device_type,
            host=target.host,
            port=target.port,
            username=target.credentials.username,
            password=target.credentials.password,
            timeout=30,
            auth_timeout=20,
        )
        return connection
    except NetmikoAuthenticationException:
        raise SessionError(f"Authentication failed for {target.host} — check username/password")
    except NetmikoTimeoutException:
        raise SessionError(f"Connection to {target.host} timed out — is the host reachable?")
    except Exception as exc:
        raise SessionError(f"Could not connect to {target.host}: {exc}") from exc
