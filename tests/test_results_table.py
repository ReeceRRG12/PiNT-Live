import unittest
from unittest.mock import Mock

from pint_live.arp import ArpEntry, ArpTable
from pint_live.models import InterfaceEntry, MacEntry, ParsedSwitchData
from pint_live.ui.results_table import ResultsTable


def _interface(port):
    return InterfaceEntry(port, "Up", "Forward", "Full", "1G", "No", "1")


def _render_rows(switches, arp_table=None):
    # Exercise population without creating a Tk window or requiring a display.
    table = object.__new__(ResultsTable)
    table._arp_table = arp_table
    table._tree = Mock()
    table._tree.get_children.return_value = ()
    table.populate(switches)
    return [
        call.kwargs
        for call in table._tree.insert.call_args_list
        if call.kwargs["tags"] != ("switch",)
    ]


class ResultsTableTests(unittest.TestCase):
    def test_duplicate_hosts_keep_their_own_mac_and_arp_snapshots(self):
        switches = [
            ParsedSwitchData(
                host="192.0.2.1",
                interfaces=[_interface("1/1/1")],
                mac_table=[MacEntry(mac, "1/1/1", "1", "Dynamic")],
            )
            for mac in ("0000.0000.0001", "0000.0000.0002")
        ]
        arp = ArpTable(entries=[
            ArpEntry("192.0.2.11", "000000000001", "first-device"),
            ArpEntry("192.0.2.12", "000000000002", "second-device"),
        ])

        rows = _render_rows(switches, arp)

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]["values"][5:8],
            ["0000.0000.0001", "192.0.2.11", "first-device"],
        )
        self.assertEqual(
            rows[1]["values"][5:8],
            ["0000.0000.0002", "192.0.2.12", "second-device"],
        )

    def test_macs_remain_grouped_by_port_with_and_without_arp(self):
        switch = ParsedSwitchData(
            host="192.0.2.1",
            interfaces=[_interface("1/1/1"), _interface("1/1/2")],
            mac_table=[
                MacEntry("0000.0000.0001", "1/1/1", "1", "Dynamic"),
                MacEntry("0000.0000.0002", "1/1/1", "1", "Dynamic"),
            ],
        )
        arp = ArpTable(entries=[ArpEntry("192.0.2.11", "000000000001", "device")])

        for table in (None, arp):
            with self.subTest(arp_loaded=table is not None):
                rows = _render_rows([switch], table)
                self.assertEqual([row["text"] for row in rows], ["1/1/1", "1/1/2"])
                self.assertEqual(rows[0]["values"][5], "0000.0000.0001, 0000.0000.0002")
                self.assertEqual(rows[1]["values"][5], "")
                if table is not None:
                    self.assertEqual(rows[0]["values"][6:8], ["192.0.2.11, ", "device"])
                    self.assertEqual(rows[1]["values"][6:8], ["", ""])


if __name__ == "__main__":
    unittest.main()
