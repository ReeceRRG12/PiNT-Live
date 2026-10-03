import unittest
from unittest.mock import patch

from netmiko import ConnectHandler

from pint_live.core.session import Credentials, SwitchTarget, open_session
from pint_live.vendors import REGISTRY


class SessionPortTests(unittest.TestCase):
    def _offline_session(self, target, device_type):
        # Exercise the installed Netmiko driver without opening a socket.
        with patch(
            "pint_live.core.session.ConnectHandler",
            side_effect=lambda **kwargs: ConnectHandler(auto_connect=False, **kwargs),
        ):
            return open_session(target, device_type=device_type)

    def test_each_vendor_uses_default_port_for_selected_protocol(self):
        target = SwitchTarget("192.0.2.1", Credentials("user", "password"))
        for vendor, config in REGISTRY.items():
            for protocol, expected_port in (("ssh", 22), ("telnet", 23)):
                with self.subTest(vendor=vendor, protocol=protocol):
                    connection = self._offline_session(
                        target, config[f"device_type_{protocol}"],
                    )
                    self.assertEqual(connection.port, expected_port)
                    self.assertEqual(connection.protocol, protocol)

    def test_explicit_port_is_preserved_for_both_protocols(self):
        target = SwitchTarget("192.0.2.1", Credentials("user", "password"), port=2223)
        for protocol in ("ssh", "telnet"):
            with self.subTest(protocol=protocol):
                connection = self._offline_session(
                    target, REGISTRY["Ruckus"][f"device_type_{protocol}"],
                )
                self.assertEqual(connection.port, 2223)


if __name__ == "__main__":
    unittest.main()
