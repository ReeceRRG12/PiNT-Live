import unittest
from unittest.mock import Mock, patch

from pint_live.ui.sidebar import Sidebar, _SwitchRow, _parse_switch_list, _present_modal


class _Entry:
    def __init__(self, text=""):
        self.text = text

    def get(self):
        return self.text

    def insert(self, index, text):
        self.text = text + self.text


def _row(row_id, host="", vendor="Ruckus", username="", password=""):
    row = object.__new__(_SwitchRow)
    row.row_id = row_id
    row.entry = _Entry(host)
    row.vendor = vendor
    row.username = username
    row.password = password
    row.failed = False
    row._vendor_label = Mock()
    row.destroy = Mock()
    return row


def _sidebar(rows):
    sidebar = object.__new__(Sidebar)
    sidebar._switch_rows = list(rows)
    sidebar._failed_row_ids = set()
    sidebar._busy = False
    sidebar._submitting = False
    sidebar._protocol = Mock(get=Mock(return_value="SSH"))
    sidebar._max_workers = Mock(get=Mock(return_value="1"))
    sidebar.shared_username = "shared-user"
    sidebar.shared_password = "shared-pass"
    sidebar.use_shared_creds = True
    sidebar._poll_btn = Mock()
    sidebar._stop_btn = Mock()
    sidebar._retry_btn = Mock()
    sidebar._credentials_label = Mock()
    sidebar.on_poll_requested = Mock()
    sidebar.winfo_toplevel = Mock(return_value=None)

    def add_row():
        row = _row(f"new-{len(sidebar._switch_rows)}")
        sidebar._switch_rows.append(row)
        return row

    sidebar._add_switch_row = Mock(side_effect=add_row)
    return sidebar


class BulkSwitchTests(unittest.TestCase):
    def test_mixed_separators_preserve_ipv6_and_skip_duplicate_hosts(self):
        hosts = _parse_switch_list(
            " 192.0.2.1\r\nSWITCH-A,192.0.2.2;2001:db8::1\tfe80::1%eth0 "
            "switch-a 2001:DB8::1;192.0.2.1 ",
            existing=["Switch-A", "192.0.2.3"],
        )
        self.assertEqual(hosts, ["192.0.2.1", "192.0.2.2", "2001:db8::1", "fe80::1%eth0"])
        self.assertEqual(_parse_switch_list("\n , ; \t"), [])

    def test_append_reuses_empty_rows_and_preserves_existing_settings(self):
        configured = _row("configured", "Switch-A", "Cisco IOS", "admin-a", "secret-a")
        empty = _row("empty", vendor="Cisco IOS", username="admin-b", password="secret-b")
        sidebar = _sidebar([configured, empty])
        sidebar.set_failed_switches({"configured", "empty"})

        added = sidebar._add_switches_from_text("switch-a,192.0.2.2\n192.0.2.3;192.0.2.2")

        self.assertEqual(added, 2)
        self.assertEqual([row.ip for row in sidebar.switch_rows], ["Switch-A", "192.0.2.2", "192.0.2.3"])
        self.assertEqual((configured.vendor, configured.username, configured.password),
                         ("Cisco IOS", "admin-a", "secret-a"))
        self.assertEqual((empty.vendor, empty.username, empty.password),
                         ("Cisco IOS", "admin-b", "secret-b"))
        self.assertEqual(sidebar._failed_row_ids, {"configured"})
        self.assertFalse(empty.failed)
        sidebar._add_switch_row.assert_called_once()

    def test_duplicate_only_paste_does_not_add_rows(self):
        sidebar = _sidebar([_row("existing", "SWITCH-A"), _row("empty")])
        self.assertEqual(sidebar._add_switches_from_text("switch-a;SWITCH-A"), 0)
        sidebar._add_switch_row.assert_not_called()
        self.assertEqual(sidebar.switch_rows[1].ip, "")

    def test_reused_empty_row_does_not_regain_an_old_poll_failure(self):
        empty = _row("old-failure", vendor="Cisco IOS", username="admin", password="secret")
        still_failed = _row("still-failed", "192.0.2.2")
        sidebar = _sidebar([empty, still_failed])
        original_failures = {"old-failure", "still-failed"}
        sidebar.set_failed_switches(original_failures)

        sidebar._add_switches_from_text("192.0.2.3")
        # A running poll can subsequently report its original row identities.
        sidebar.set_failed_switches(original_failures)

        self.assertNotEqual(empty.row_id, "old-failure")
        self.assertEqual((empty.vendor, empty.username, empty.password),
                         ("Cisco IOS", "admin", "secret"))
        self.assertFalse(empty.failed)
        self.assertEqual(sidebar._retry_rows(), [still_failed])
        sidebar._retry_btn.configure.assert_called_with(text="Retry failed (1)", state="normal")

    def test_multiline_modal_does_not_bind_return_to_save(self):
        dialog, parent = Mock(), Mock()
        _present_modal(dialog, parent, 540, 420, submit_on_return=False)
        self.assertEqual([call.args[0] for call in dialog.bind.call_args_list], ["<Escape>"])
        dialog.reset_mock()
        _present_modal(dialog, parent, 540, 420)
        self.assertEqual([call.args[0] for call in dialog.bind.call_args_list], ["<Escape>", "<Return>"])


class RetrySwitchTests(unittest.TestCase):
    def test_retry_uses_failed_row_identity_and_current_configuration(self):
        successful = _row("successful", "192.0.2.1")
        failed = _row("failed", "192.0.2.1", username="old-user", password="old-pass")
        unrelated = _row("new", "192.0.2.3")
        sidebar = _sidebar([successful, failed, unrelated])
        sidebar.set_failed_switches({"failed"})

        sidebar.use_shared_creds = False
        sidebar.shared_username = sidebar.shared_password = ""
        failed.username, failed.password = "corrected-user", "corrected-pass"
        failed.vendor = "Cisco IOS"
        sidebar._protocol.get.return_value = "Telnet"
        sidebar._max_workers.get.return_value = "20"

        with patch("pint_live.ui.sidebar.messagebox") as messages:
            sidebar._on_retry_click()

        messages.showwarning.assert_not_called()
        messages.askyesno.assert_not_called()
        config = sidebar.on_poll_requested.call_args.args[0]
        self.assertEqual(config["switches"], [{
            "row_id": "failed", "host": "192.0.2.1", "vendor": "Cisco IOS",
            "username": "corrected-user", "password": "corrected-pass",
        }])
        self.assertTrue(config["retry_failed"])
        self.assertEqual(config["protocol"], "Telnet")
        self.assertEqual(config["max_workers"], 20)
        self.assertTrue(failed.failed)
        self.assertFalse(successful.failed)

    def test_retry_resolves_changed_shared_credentials(self):
        sidebar = _sidebar([_row("failed", "192.0.2.1", username="stale", password="stale")])
        sidebar.set_failed_switches({"failed"})
        sidebar.shared_username = "corrected-shared-user"
        sidebar.shared_password = "corrected-shared-pass"
        sidebar._on_retry_click()
        switch = sidebar.on_poll_requested.call_args.args[0]["switches"][0]
        self.assertEqual((switch["username"], switch["password"]),
                         ("corrected-shared-user", "corrected-shared-pass"))

    def test_removed_failed_rows_and_new_rows_are_not_retried(self):
        failed = _row("failed", "192.0.2.1")
        sidebar = _sidebar([failed, _row("other", "192.0.2.2")])
        sidebar.set_failed_switches({"failed", "already-removed"})
        sidebar._remove_switch_row(failed)
        sidebar._add_switches_from_text("192.0.2.1")
        sidebar._on_retry_click()
        sidebar.on_poll_requested.assert_not_called()
        failed.destroy.assert_called_once()
        self.assertEqual(sidebar._failed_row_ids, set())
        sidebar._retry_btn.configure.assert_called_with(text="Retry failed (0)", state="disabled")

    def test_blank_failed_row_is_not_eligible_and_edit_refreshes_count(self):
        failed = _row("failed", "192.0.2.1")
        sidebar = _sidebar([failed])
        sidebar.set_failed_switches({"failed"})
        sidebar._retry_btn.configure.assert_called_with(text="Retry failed (1)", state="normal")
        failed.entry.text = ""
        sidebar._on_switch_edited()
        sidebar._on_retry_click()
        sidebar.on_poll_requested.assert_not_called()
        sidebar._retry_btn.configure.assert_called_with(text="Retry failed (0)", state="disabled")

    def test_retry_button_and_repeat_requests_are_blocked_while_busy(self):
        sidebar = _sidebar([_row("failed", "192.0.2.1")])
        sidebar.set_failed_switches({"failed"})
        sidebar._on_retry_click()
        sidebar._on_retry_click()
        sidebar._on_poll_click()
        sidebar.on_poll_requested.assert_called_once()
        sidebar._retry_btn.configure.assert_called_with(text="Retry failed (1)", state="disabled")
        sidebar.set_busy(False)
        sidebar._retry_btn.configure.assert_called_with(text="Retry failed (1)", state="normal")

    def test_missing_credentials_on_failed_row_leave_controls_available(self):
        sidebar = _sidebar([_row("failed", "192.0.2.1")])
        sidebar.set_failed_switches({"failed"})
        sidebar.shared_password = ""
        with patch("pint_live.ui.sidebar.messagebox.showwarning") as warning:
            sidebar._on_retry_click()
        warning.assert_called_once()
        sidebar.on_poll_requested.assert_not_called()
        self.assertFalse(sidebar._busy)
        self.assertFalse(sidebar._submitting)

    def test_regular_poll_preserves_row_ids_and_defaults_to_one_worker(self):
        sidebar = _sidebar([_row("first", "192.0.2.1"), _row("second", "192.0.2.2")])
        sidebar._on_poll_click()
        config = sidebar.on_poll_requested.call_args.args[0]
        self.assertFalse(config["retry_failed"])
        self.assertEqual(config["max_workers"], 1)
        self.assertEqual([switch["row_id"] for switch in config["switches"]], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
