import unittest
from unittest.mock import Mock

from pint_live.arp import ArpEntry, ArpTable
from pint_live.models import InterfaceEntry, MacEntry, ParsedSwitchData
from pint_live.ui.results_table import ResultsTable


def _interface(port):
    return InterfaceEntry(port, "Up", "Forward", "Full", "1G", "No", "1")


def _render_rows(switches, arp_table=None, **filters):
    # Exercise population without creating a Tk window or requiring a display.
    table = object.__new__(ResultsTable)
    table._arp_table = arp_table
    table._tree = Mock()
    table._tree.get_children.return_value = ()
    table.populate(switches, **filters)
    return [
        call.kwargs
        for call in table._tree.insert.call_args_list
        if call.kwargs["tags"] != ("switch",)
    ]


class ResultsTableTests(unittest.TestCase):
    def test_native_table_dimensions_follow_display_scaling(self):
        table = object.__new__(ResultsTable)
        table._arp_table = None
        table._tree = Mock()
        table._style = Mock()
        table._get_widget_scaling = Mock(return_value=2.0)
        table._apply_tree_scaling()
        table._configure_columns()
        self.assertEqual(table._style.configure.call_args_list[0].kwargs["rowheight"], 64)
        self.assertEqual(table._style.configure.call_args_list[0].kwargs["font"][1], -26)
        table._tree.column.assert_any_call("#0", width=500, minwidth=500, stretch=False)

    def test_search_matches_switch_and_port_fields_together(self):
        switch = ParsedSwitchData(
            host="192.0.2.1", hostname="ACCESS-LOBBY", model="ICX 7150",
            interfaces=[_interface("1/1/1"), _interface("1/1/2")],
        )
        rows = _render_rows([switch], query="lobby 1/1/2")
        self.assertEqual([row["text"] for row in rows], ["1/1/2"])
        self.assertEqual(_render_rows([switch], query="missing"), [])
        self.assertEqual(len(_render_rows([switch], query="192.0.2.1 icx")), 2)

    def test_state_filter_combines_with_arp_search(self):
        switch = ParsedSwitchData(
            host="192.0.2.1", interfaces=[_interface("1/1/1")],
            mac_table=[MacEntry("0000.0000.0001", "1/1/1", "1", "Dynamic")],
        )
        arp = ArpTable(entries=[ArpEntry("192.0.2.11", "000000000001", "Lobby-AP")])
        self.assertEqual(len(_render_rows([switch], arp, query="lobby-ap", link_filter="Up")), 1)
        self.assertEqual(_render_rows([switch], arp, query="lobby-ap", link_filter="Down"), [])
        self.assertEqual(len(switch.interfaces), 1)  # Filtering never changes export data.

    def test_empty_switch_groups_are_omitted(self):
        table = object.__new__(ResultsTable)
        table._arp_table = None
        table._tree = Mock()
        table._tree.get_children.return_value = ()
        shown = table.populate([ParsedSwitchData(host="192.0.2.1", interfaces=[_interface("1/1/1")])], query="no-match")
        self.assertEqual(shown, 0)
        table._tree.insert.assert_not_called()

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
                    self.assertEqual(rows[0]["values"][6:8], ["192.0.2.11, ", "device, "])
                    self.assertEqual(rows[1]["values"][6:8], ["", ""])

    def test_missing_hostnames_keep_their_mac_and_ip_positions(self):
        switch = ParsedSwitchData(
            host="192.0.2.1", interfaces=[_interface("1/1/1")],
            mac_table=[
                MacEntry(f"0000.0000.000{index}", "1/1/1", "1", "Dynamic")
                for index in range(1, 4)
            ],
        )
        arp = ArpTable(entries=[
            ArpEntry("192.0.2.11", "000000000001"),
            ArpEntry("192.0.2.12", "000000000002", "second-device"),
        ])

        rows = _render_rows([switch], arp)

        self.assertEqual(rows[0]["values"][5:8], [
            "0000.0000.0001, 0000.0000.0002, 0000.0000.0003",
            "192.0.2.11, 192.0.2.12, ",
            ", second-device, ",
        ])


if __name__ == "__main__":
    unittest.main()
