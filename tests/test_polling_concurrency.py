import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from netmiko.exceptions import ReadTimeout

from pint_live.core.polling import PollCancelled, run_poll
from pint_live.core.session import Credentials
from pint_live.models import InterfaceEntry, ParsedSwitchData


def _parsed(host):
    return ParsedSwitchData(
        host=host,
        interfaces=[InterfaceEntry("1/1/1", "Up", "Forward", "Full", "1G", "No", "1")],
    )


def _job(host, collect, row_id=None):
    job = {
        "host": host,
        "vendor": "Ruckus",
        "device_type": "ruckus_fastiron",
        "collector": SimpleNamespace(collect=collect),
        "parser": SimpleNamespace(parse=lambda raw: raw),
        "credentials": Credentials("user", "password"),
    }
    if row_id is not None:
        job["row_id"] = row_id
    return job


class ConcurrentPollingTests(unittest.TestCase):
    def test_reaches_but_never_exceeds_selected_session_limit(self):
        for limit in (1, 2, 20):
            with self.subTest(limit=limit):
                lock = threading.Lock()
                ready = threading.Event()
                active = 0
                peak = 0
                disconnects = {}
                worker_daemons = []
                progress = []

                def connect(target, **kwargs):
                    nonlocal active, peak
                    with lock:
                        active += 1
                        peak = max(peak, active)
                        worker_daemons.append(threading.current_thread().daemon)
                        if active == limit:
                            ready.set()

                    def disconnect():
                        nonlocal active
                        with lock:
                            active -= 1
                            disconnects[target.host] = disconnects.get(target.host, 0) + 1

                    return SimpleNamespace(disconnect=disconnect)

                def collect(connection, host, stop_requested):
                    self.assertTrue(ready.wait(3), "Workers did not run concurrently")
                    return _parsed(host)

                jobs = [_job(f"192.0.2.{index + 1}", collect) for index in range(23)]
                results, errors, stopped, outcomes = run_poll(
                    jobs, threading.Event(), limit, connect, lambda *args: None, progress.append,
                )

                self.assertEqual(peak, limit)
                self.assertEqual(active, 0)
                self.assertTrue(all(worker_daemons))
                self.assertEqual(disconnects, {job["host"]: 1 for job in jobs})
                self.assertEqual([result.host for result in results], [job["host"] for job in jobs])
                self.assertEqual(errors, [])
                self.assertFalse(stopped)
                self.assertEqual(list(outcomes), list(range(len(jobs))))
                self.assertEqual(progress, [(index + 1) / len(jobs) for index in range(len(jobs))])

    def test_results_errors_and_row_outcomes_follow_input_order(self):
        first_completed = threading.Event()
        completed_hosts = []

        def collect(connection, host, stop_requested):
            if host != "192.0.2.3":
                self.assertTrue(first_completed.wait(3))
            if host == "192.0.2.2":
                raise ValueError("bad credentials")
            completed_hosts.append(host)
            return _parsed(host)

        jobs = [_job(f"192.0.2.{index}", collect, f"row-{index}") for index in (1, 2, 3)]
        results, errors, stopped, outcomes = run_poll(
            jobs, threading.Event(), 3, lambda *args, **kwargs: Mock(),
            lambda *args: None, lambda progress: first_completed.set(),
        )

        self.assertEqual(completed_hosts, ["192.0.2.3", "192.0.2.1"])
        self.assertEqual([result.host for result in results], ["192.0.2.1", "192.0.2.3"])
        self.assertEqual(errors, [("192.0.2.2", "bad credentials")])
        self.assertEqual(list(outcomes), ["row-1", "row-2", "row-3"])
        self.assertEqual(outcomes["row-2"], (None, "bad credentials"))
        self.assertFalse(stopped)

    def test_stop_cancels_active_jobs_and_does_not_connect_queued_jobs(self):
        stop = threading.Event()
        both_active = threading.Barrier(2, timeout=3)
        connections = []
        connected_hosts = []

        def connect(target, **kwargs):
            connected_hosts.append(target.host)
            connection = Mock()
            connections.append(connection)
            return connection

        def collect(connection, host, stop_requested):
            both_active.wait()
            stop.set()
            self.assertTrue(stop_requested())
            raise PollCancelled()

        results, errors, stopped, outcomes = run_poll(
            [_job(f"192.0.2.{index}", collect) for index in range(1, 8)],
            stop, 2, connect, lambda *args: None, lambda progress: None,
        )

        self.assertEqual(set(connected_hosts), {"192.0.2.1", "192.0.2.2"})
        self.assertEqual(results, [])
        self.assertEqual(errors, [])
        self.assertEqual(outcomes, {})
        self.assertTrue(stopped)
        for connection in connections:
            connection.disconnect.assert_called_once()

    def test_stop_during_last_command_keeps_completed_data(self):
        stop = threading.Event()
        connection = Mock()

        def collect(connection, host, stop_requested):
            stop.set()
            return _parsed(host)

        results, errors, stopped, outcomes = run_poll(
            [_job("192.0.2.1", collect, "row")], stop, 1,
            lambda *args, **kwargs: connection, lambda *args: None, lambda progress: None,
        )

        self.assertEqual([result.host for result in results], ["192.0.2.1"])
        self.assertEqual(errors, [])
        self.assertTrue(stopped)
        self.assertIs(outcomes["row"][0], results[0])
        connection.disconnect.assert_called_once()

    def test_read_timeout_retries_with_a_new_connection(self):
        connections = [Mock(), Mock()]
        connect = Mock(side_effect=connections)
        collect = Mock(side_effect=[ReadTimeout("prompt lost"), _parsed("192.0.2.1")])
        results, errors, stopped, outcomes = run_poll(
            [_job("192.0.2.1", collect)], threading.Event(), 1,
            connect, lambda *args: None, lambda progress: None,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(errors, [])
        self.assertFalse(stopped)
        self.assertEqual(connect.call_count, 2)
        for connection in connections:
            connection.disconnect.assert_called_once()

    def test_stop_during_timeout_cleanup_prevents_retry(self):
        stop = threading.Event()
        connection = Mock()
        connection.disconnect.side_effect = stop.set
        connect = Mock(return_value=connection)
        collect = Mock(side_effect=ReadTimeout("prompt lost"))

        results, errors, stopped, outcomes = run_poll(
            [_job("192.0.2.1", collect)], stop, 1,
            connect, lambda *args: None, lambda progress: None,
        )

        self.assertEqual(results, [])
        self.assertEqual(errors, [])
        self.assertEqual(outcomes, {})
        self.assertTrue(stopped)
        connect.assert_called_once()
        connection.disconnect.assert_called_once()

    def test_stop_before_connecting_skips_target(self):
        stop = threading.Event()
        connect = Mock()
        results, errors, stopped, outcomes = run_poll(
            [_job("192.0.2.1", Mock())], stop, 2,
            connect, lambda *args: stop.set(), lambda progress: None,
        )

        connect.assert_not_called()
        self.assertEqual((results, errors, outcomes), ([], [], {}))
        self.assertTrue(stopped)

    def test_second_read_timeout_is_a_failure_and_closes_both_sessions(self):
        connections = [Mock(), Mock()]
        connect = Mock(side_effect=connections)
        collect = Mock(side_effect=ReadTimeout("prompt lost"))
        results, errors, stopped, outcomes = run_poll(
            [_job("192.0.2.1", collect, "row")], threading.Event(), 1,
            connect, lambda *args: None, lambda progress: None,
        )

        self.assertEqual(results, [])
        self.assertEqual(errors, [("192.0.2.1", "Timed out waiting for the switch response")])
        self.assertEqual(outcomes, {"row": (None, errors[0][1])})
        self.assertFalse(stopped)
        self.assertEqual(connect.call_count, 2)
        for connection in connections:
            connection.disconnect.assert_called_once()

    def test_invalid_limits_do_not_open_connections(self):
        for limit in (0, 21, -1, 1.5, "2", True, None):
            with self.subTest(limit=limit):
                connect = Mock()
                with self.assertRaises(ValueError):
                    run_poll([], threading.Event(), limit, connect, Mock(), Mock())
                connect.assert_not_called()

    def test_duplicate_hosts_keep_separate_row_outcomes(self):
        good = _job("192.0.2.1", lambda connection, host, stop: _parsed(host), "good-row")
        bad = _job("192.0.2.1", Mock(side_effect=ValueError("authentication failed")), "bad-row")
        results, errors, stopped, outcomes = run_poll(
            [good, bad], threading.Event(), 2,
            lambda *args, **kwargs: Mock(), lambda *args: None, lambda progress: None,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(errors, [("192.0.2.1", "authentication failed")])
        self.assertEqual(list(outcomes), ["good-row", "bad-row"])
        self.assertIs(outcomes["good-row"][0], results[0])
        self.assertEqual(outcomes["bad-row"], (None, "authentication failed"))


if __name__ == "__main__":
    unittest.main()
