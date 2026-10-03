import unittest
from types import SimpleNamespace

from pint_live.parsers.cisco_ios import parse


def _raw(config="", version=""):
    return SimpleNamespace(
        host="192.0.2.1",
        version_output=version,
        interfaces_output=(
            "Port      Name               Status       Vlan       Duplex  Speed Type\n"
            "Gi1/0/1   UPLINK             connected    trunk        full   1000 10/100/1000BaseTX\n"
            "Gi1/0/2                      notconnect   20           auto   auto 10/100/1000BaseTX\n"
        ),
        mac_table_output="   20    aabb.cc11.2233    DYNAMIC     Gi1/0/2\n",
        running_config_output=config,
    )


def _trunk_config(*expressions):
    return "interface GigabitEthernet1/0/1\n" + "".join(
        f" switchport trunk allowed vlan {expression}\n" for expression in expressions
    ) + "!\n"


class CiscoParserTests(unittest.TestCase):
    def test_hardware_model_is_not_taken_from_software_banner(self):
        for banner, hardware, firmware, model in [
            (
                "Cisco IOS Software, C2960X Software, Version 15.2(7)E4, RELEASE SOFTWARE (fc2)",
                "cisco WS-C2960X-48FPS-L (APM86XXX) processor (revision H0) with 524288K bytes of memory.",
                "15.2(7)E4", "WS-C2960X-48FPS-L",
            ),
            (
                "Cisco IOS XE Software, Version 17.09.04a",
                "cisco C9200L-48P-4X (ARM64) processor (revision 1) with 793732K/6147K bytes of memory.",
                "17.09.04a", "C9200L-48P-4X",
            ),
        ]:
            with self.subTest(model=model):
                data = parse(_raw(version=f"{banner}\nSwitch01 uptime is 2 weeks\n{hardware}\n"))
                self.assertEqual(data.model, model)
                self.assertEqual(data.firmware, firmware)
                self.assertEqual(data.hostname, "Switch01")

    def test_software_only_output_does_not_invent_a_hardware_model(self):
        data = parse(_raw(version="Cisco IOS Software, C2960X Software, Version 15.2(7)E4\n"))
        self.assertEqual(data.model, "")

    def test_add_remove_ranges_preserve_prior_list_and_vlan_names(self):
        config = (
            "vlan 10\n name USERS\n!\nvlan 20\n name SERVERS\n!\n"
            + _trunk_config("10,20-22", "add 21,30-32", "remove 22,31-32")
            + "interface GigabitEthernet1/0/2\n description SERVER\n switchport access vlan 20\n!\n"
        )
        data = parse(_raw(config))
        self.assertEqual(data.interfaces[0].tagged_vlans, "10 (USERS), 20 (SERVERS), 21, 30")
        self.assertEqual(data.interfaces[0].description, "UPLINK")
        self.assertEqual(data.interfaces[1].description, "SERVER")
        self.assertEqual(data.interfaces[1].untagged_vlan, "20 (SERVERS)")
        self.assertEqual(data.mac_table[0].mac, "AABB.CC11.2233")

    def test_commands_apply_in_order_including_default_all(self):
        cases = [
            (("add 10-20",), "All (1-4094)"),
            (("remove 10-12",), "All except 10, 11, 12"),
            (("10-12", "add 20", "30,40"), "30, 40"),
            (("none", "add 10-12", "remove 11"), "10, 12"),
            (("10-12", "all", "remove 20"), "All except 20"),
            (("10-12", "except 20-22", "add 21", "remove 30"), "All except 20, 22, 30"),
            (("10-12", "none"), "None"),
            (("10-12", "remove 10-12"), "None"),
            (("none", "add 4093-4094,1"), "1, 4093, 4094"),
        ]
        for commands, expected in cases:
            with self.subTest(commands=commands):
                self.assertEqual(parse(_raw(_trunk_config(*commands))).interfaces[0].tagged_vlans, expected)

    def test_no_command_restores_all_vlans(self):
        config = (
            "interface GigabitEthernet1/0/1\n"
            " switchport trunk allowed vlan 10-20\n"
            " no switchport trunk allowed vlan\n!\n"
        )
        self.assertEqual(parse(_raw(config)).interfaces[0].tagged_vlans, "All (1-4094)")

    def test_malformed_vlan_lines_preserve_previous_list_and_ports(self):
        for invalid in ["add", "add 10-", "10-2", "0", "4095", "1-999999999", "10,bad", "except none"]:
            with self.subTest(invalid=invalid):
                data = parse(_raw(_trunk_config("20", invalid)))
                self.assertEqual(len(data.interfaces), 2)
                self.assertEqual(data.interfaces[0].tagged_vlans, "20")

    def test_config_is_kept_per_interface(self):
        config = (
            _trunk_config("none", "add 10-12")
            + "interface GigabitEthernet1/0/2\n switchport trunk allowed vlan 20\n!\n"
        )
        data = parse(_raw(config))
        self.assertEqual(data.interfaces[0].tagged_vlans, "10, 11, 12")
        self.assertEqual(data.interfaces[1].tagged_vlans, "20")


if __name__ == "__main__":
    unittest.main()
