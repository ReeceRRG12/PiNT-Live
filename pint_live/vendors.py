"""Vendor registry — maps vendor names to their collectors, parsers, and Netmiko device types."""

from pint_live.collectors import ruckus as _ruckus_col
from pint_live.collectors import cisco_ios as _cisco_col
from pint_live.collectors import hp_aruba as _hp_col

from pint_live.parsers import ruckus as _ruckus_par
from pint_live.parsers import cisco_ios as _cisco_par
from pint_live.parsers import hp_aruba as _hp_par


REGISTRY: dict[str, dict] = {
    "Ruckus": {
        "supported":           True,
        "device_type_ssh":     "ruckus_fastiron",
        "device_type_telnet":  "ruckus_fastiron_telnet",
        "collector":           _ruckus_col,
        "parser":              _ruckus_par,
    },
    "Cisco IOS": {
        "supported":           True,
        "device_type_ssh":     "cisco_ios",
        "device_type_telnet":  "cisco_ios_telnet",
        "collector":           _cisco_col,
        "parser":              _cisco_par,
    },
    "HP/Aruba": {
        "supported":           True,
        "device_type_ssh":     "hp_procurve",
        "device_type_telnet":  "hp_procurve_telnet",
        "collector":           _hp_col,
        "parser":              _hp_par,
    },
}
