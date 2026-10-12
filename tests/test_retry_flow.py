"""Exercise poll/retry application state without Tk or live connections."""

import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pint_live.models import InterfaceEntry, ParsedSwitchData
from pint_live.ui.app import PintLiveApp, VENDORS


def _switch(row_id, host, **overrides):
    switch = {
        "row_id": row_id,
        "host": host,
        "vendor": "Ruckus",
        "username": "operator",
        "password": "old-password",
    }
    switch.update(overrides)
    return switch


def _config(switches, **overrides):
    config = {"switches": switches, "protocol": "SSH", "max_workers": 3}
    config.update(overrides)
    return config


def _parsed(host, hostname):
    return ParsedSwitchData(
        host=host, hostname=hostname,
        interfaces=[InterfaceEntry("1/1/1", "Up", "Forward", "Full", "1G", "No", "1")],
    )


def _app():
    app = object.__new__(PintLiveApp)
    app._poll_results = []
    app._results_by_row = {}
    app._failed_row_ids = set()
    app._poll_order = []
    app._polling = False
    app._stop_event = threading.Event()
    app._search_after = None
    app._sidebar = Mock()
    app._results_table = Mock()
    app._results_table.populate.return_value = 1
    app._search = Mock()
    app._search.get.return_value = ""
    app._link_filter = Mock()
    app._link_filter.get.return_value = "All ports"
    app._export_btn = Mock()
    app._empty_title = Mock()
    app._empty_description = Mock()
    app._empty_state = Mock()
    app._results_caption = Mock()
    app._metric_values = {key: Mock() for key in ("switches", "ports", "up", "macs")}
    app._navigate = Mock()
    return app


class RetryFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        self.thread = self.enterContext(patch("pint_live.ui.app.threading.Thread"))
        self.dialogs = self.enterContext(patch("pint_live.ui.app.messagebox"))

    def _finish(self, outcomes, *, stopped=False):
        results = [parsed for parsed, error in outcomes.values() if parsed is not None]
        errors = [(row_id, error) for row_id, (parsed, error) in outcomes.items() if error]
        self.app._on_poll_finished(results, errors, stopped, outcomes)

    def test_retry_uses_corrected_settings_and_preserves_duplicate_host_success(self):
        same_host = "192.0.2.10"
        first = _parsed(same_host, "first snapshot")
        second = _parsed("192.0.2.20", "corrected switch")
        self.app._start_poll(_config([
            _switch("row-a", same_host), _switch("row-b", same_host),
        ]))
        self._finish({"row-a": (first, None), "row-b": (None, "Authentication failed")})
        self.app._results_table.clear.reset_mock()
        self.app._search.delete.reset_mock()

        corrected = _config([
            _switch("row-a", same_host),
            _switch("row-b", "192.0.2.20", vendor="Cisco IOS", username="new-user", password="new-password"),
        ], retry_failed=True, protocol="Telnet", max_workers=20)
        self.app._start_poll(corrected)
        jobs, concurrency = self.thread.call_args.kwargs["args"]

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["row_id"], "row-b")
        self.assertEqual(job["host"], "192.0.2.20")
        self.assertEqual(job["vendor"], "Cisco IOS")
        self.assertEqual(job["device_type"], "cisco_ios_telnet")
        self.assertIs(job["collector"], VENDORS["Cisco IOS"]["collector"])
        self.assertIs(job["parser"], VENDORS["Cisco IOS"]["parser"])
        self.assertEqual((job["credentials"].username, job["credentials"].password), ("new-user", "new-password"))
        self.assertEqual(concurrency, 20)
        self.assertEqual(self.app._poll_results, [first])
        self.app._results_table.clear.assert_not_called()
        self.app._search.delete.assert_not_called()

        # Changes after Start cannot alter the background worker's credentials.
        corrected["switches"][1]["password"] = "edited-after-start"
        self.assertEqual(job["credentials"].password, "new-password")
        self._finish({"row-b": (second, None)})
        self.assertEqual(self.app._poll_results, [first, second])
        self.assertIs(self.app._poll_results[0], first)
        self.assertEqual(self.app._failed_row_ids, set())
        self.app._sidebar.set_failed_switches.assert_called_with(set())
        self.app._export_btn.configure.assert_called_with(state="normal")

    def test_full_poll_clears_previous_successes_failures_and_filters(self):
        old = _parsed("192.0.2.1", "old switch")
        self.app._start_poll(_config([
            _switch("old-good", old.host), _switch("old-failed", "192.0.2.2"),
        ]))
        self._finish({"old-good": (old, None), "old-failed": (None, "No connection")})
        self.app._results_table.clear.reset_mock()
        self.app._search.delete.reset_mock()
        self.app._stop_event.set()

        self.app._start_poll(_config([_switch("new-row", "192.0.2.3")], max_workers=1))

        self.assertEqual(self.app._poll_results, [])
        self.assertEqual(self.app._results_by_row, {})
        self.assertEqual(self.app._failed_row_ids, set())
        self.assertEqual(self.app._poll_order, ["new-row"])
        self.assertFalse(self.app._stop_event.is_set())
        self.app._results_table.clear.assert_called_once()
        self.app._search.delete.assert_called_once_with(0, "end")
        self.app._link_filter.set.assert_called_with("All ports")
        self.app._sidebar.set_failed_switches.assert_called_with(set())
        self.app._metric_values["switches"].configure.assert_called_with(text="0")

        new = _parsed("192.0.2.3", "new switch")
        self._finish({"new-row": (new, None)})
        self.assertEqual(self.app._poll_results, [new])

    def test_cancelled_retry_keeps_unfinished_failures_and_completed_results(self):
        switches = [_switch(f"row-{number}", f"192.0.2.{number}") for number in range(1, 4)]
        first = _parsed("192.0.2.1", "existing success")
        second = _parsed("192.0.2.2", "recovered success")
        self.app._start_poll(_config(switches))
        self._finish({
            "row-1": (first, None),
            "row-2": (None, "Bad credentials"),
            "row-3": (None, "Bad credentials"),
        })

        self.app._start_poll(_config(switches, retry_failed=True))
        self._finish({"row-2": (second, None)}, stopped=True)

        self.assertEqual(self.app._poll_results, [first, second])
        self.assertEqual(self.app._failed_row_ids, {"row-3"})
        self.assertFalse(self.app._polling)
        self.app._sidebar.set_failed_switches.assert_called_with({"row-3"})
        self.app._export_btn.configure.assert_called_with(state="normal")

        self.app._start_poll(_config(switches, retry_failed=True))
        jobs, _ = self.thread.call_args.kwargs["args"]
        self.assertEqual([job["row_id"] for job in jobs], ["row-3"])
        self._finish({}, stopped=True)
        self.assertEqual(self.app._failed_row_ids, {"row-3"})
        self.assertEqual(self.app._poll_results, [first, second])

    def test_out_of_order_retry_merges_by_original_row_and_exports_once_per_row(self):
        duplicate_host = "192.0.2.1"
        switches = [_switch(f"row-{number}", duplicate_host) for number in range(1, 4)]
        first = _parsed(duplicate_host, "first snapshot")
        second = _parsed(duplicate_host, "second snapshot")
        third = _parsed(duplicate_host, "third snapshot")
        self.app._start_poll(_config(switches))
        self._finish({
            "row-2": (second, None),
            "row-3": (None, "Connection failed"),
            "row-1": (None, "Connection failed"),
        })

        # Input row order and worker completion order can both differ on retry.
        self.app._start_poll(_config(list(reversed(switches)), retry_failed=True))
        recovered = {"row-3": (third, None), "row-1": (first, None)}
        self._finish(recovered)
        self.assertEqual(self.app._poll_results, [first, second, third])
        self._finish(recovered)
        self.assertEqual(self.app._poll_results, [first, second, third])
        self.app._results_table.populate.assert_called_with([first, second, third], "", "All ports")

        self.app._resolve_arp_for_export = Mock(return_value=None)
        self.app._sidebar.include_raw_outputs = False
        with (
            patch("pint_live.ui.app.filedialog.asksaveasfilename", return_value="/tmp/retry-export.xlsx"),
            patch("pint_live.ui.app.excel_exporter.export", return_value=Path("/tmp/retry-export.xlsx")) as export,
        ):
            self.app._export()
        export.assert_called_once_with(
            [first, second, third], Path("/tmp/retry-export.xlsx"),
            arp_table=None, include_raw_outputs=False,
        )

    def test_retry_without_failed_rows_does_not_start_a_worker_or_clear_success(self):
        switch = _switch("row-1", "192.0.2.1")
        parsed = _parsed(switch["host"], "good switch")
        self.app._start_poll(_config([switch]))
        self._finish({"row-1": (parsed, None)})
        self.thread.reset_mock()
        self.app._results_table.clear.reset_mock()

        self.app._start_poll(_config([switch], retry_failed=True))

        self.thread.assert_not_called()
        self.app._results_table.clear.assert_not_called()
        self.assertEqual(self.app._poll_results, [parsed])
        self.assertFalse(self.app._polling)

    def test_invalid_concurrency_cannot_start_poll_or_discard_results(self):
        switch = _switch("row-1", "192.0.2.1")
        parsed = _parsed(switch["host"], "good switch")
        self.app._start_poll(_config([switch]))
        self._finish({"row-1": (parsed, None)})
        self.thread.reset_mock()

        for invalid in (0, 21, True, "4", 1.5):
            with self.subTest(concurrency=invalid):
                self.app._start_poll(_config([switch], max_workers=invalid))
                self.assertEqual(self.app._poll_results, [parsed])
                self.assertFalse(self.app._polling)
        self.thread.assert_not_called()
        self.assertEqual(self.dialogs.showwarning.call_count, 5)


if __name__ == "__main__":
    unittest.main()
