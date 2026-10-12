"""Polling with bounded concurrency and cooperative cancellation."""

from __future__ import annotations

import threading
from collections.abc import Callable

from netmiko.exceptions import ReadTimeout

from pint_live.core.session import SwitchTarget
from pint_live.models import ParsedSwitchData


class PollCancelled(Exception):
    """Raised when the user requests that an in-progress poll stop."""


def friendly_poll_error(exc: Exception) -> str:
    if isinstance(exc, ReadTimeout):
        return "Timed out waiting for the switch response"
    message = next((line.strip() for line in str(exc).splitlines() if line.strip()), "")
    return message or type(exc).__name__


def run_poll(
    jobs: list[dict],
    stop_event: threading.Event,
    max_workers: int,
    open_session: Callable,
    on_status: Callable[[str, str], None],
    on_progress: Callable[[float], None],
) -> tuple[
    list[ParsedSwitchData], list[tuple[str, str]], bool,
    dict[object, tuple[ParsedSwitchData | None, str | None]],
]:
    """Poll independent sessions, returning results in the supplied job order.

    Callbacks run on worker threads and must not access GUI widgets. Credentials
    are supplied in each job snapshot. Cancelled and unstarted jobs have no
    outcome, allowing callers to keep them distinct from failed connections.
    """
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not 1 <= max_workers <= 20:
        raise ValueError("Concurrent switches must be a whole number from 1 to 20")

    completed: dict[int, tuple[ParsedSwitchData | None, str | None]] = {}
    cancelled = threading.Event()
    lock = threading.Lock()
    next_index = 0

    def stop_requested() -> bool:
        return stop_event.is_set() or cancelled.is_set()

    def notify(callback: Callable, *args) -> None:
        # A reporting failure must not abandon sessions or lose their data.
        try:
            callback(*args)
        except Exception:
            pass

    def poll_one(job: dict) -> tuple[ParsedSwitchData | None, str | None] | None:
        host = job["host"]
        target = SwitchTarget(host=host, credentials=job["credentials"])
        for attempt in range(1, 3):
            if stop_requested():
                return None
            connection = None
            try:
                retry = " (retry)" if attempt == 2 else ""
                notify(on_status, f"Connecting to {host} ({job['vendor']}){retry}…", "info")
                if stop_requested():
                    return None
                connection = open_session(target, device_type=job["device_type"])
                if stop_requested():
                    return None
                notify(on_status, f"Collecting data from {host}{retry}…", "info")
                raw = job["collector"].collect(connection, host, stop_requested)
                parsed = job["parser"].parse(raw)
                if not parsed.interfaces:
                    raise ValueError("No interfaces were recognised in the switch output")
                up = sum(interface.link.lower() == "up" for interface in parsed.interfaces)
                notify(on_status, f"✓ {host}: {up}/{len(parsed.interfaces)} ports up", "success")
                return parsed, None
            except PollCancelled:
                cancelled.set()
                return None
            except ReadTimeout as exc:
                if stop_requested():
                    return None
                if attempt == 1:
                    notify(on_status, f"Retrying {host} after a response timeout…", "warning")
                    continue
                message = friendly_poll_error(exc)
                notify(on_status, f"✗ {host}: {message}", "error")
                return None, message
            except Exception as exc:
                message = friendly_poll_error(exc)
                notify(on_status, f"✗ {host}: {message}", "error")
                return None, message
            finally:
                if connection is not None:
                    try:
                        connection.disconnect()
                    except Exception:
                        pass
        return None

    def worker() -> None:
        nonlocal next_index
        while True:
            with lock:
                if stop_requested() or next_index >= len(jobs):
                    return
                index = next_index
                next_index += 1
            try:
                outcome = poll_one(jobs[index])
            except Exception as exc:
                outcome = None, friendly_poll_error(exc)
            if outcome is not None:
                with lock:
                    completed[index] = outcome
                    # Serialise progress notifications so completion races
                    # cannot make the displayed progress move backwards.
                    notify(on_progress, len(completed) / len(jobs))

    workers = [
        threading.Thread(target=worker, daemon=True, name=f"pint-poll-{index + 1}")
        for index in range(min(max_workers, len(jobs)))
    ]
    started = []
    try:
        for thread in workers:
            thread.start()
            started.append(thread)
    finally:
        for thread in started:
            thread.join()

    results: list[ParsedSwitchData] = []
    errors: list[tuple[str, str]] = []
    outcomes = {}
    for index, job in enumerate(jobs):
        if index not in completed:
            continue
        parsed, error = completed[index]
        outcomes[job.get("row_id", index)] = parsed, error
        if parsed is not None:
            results.append(parsed)
        elif error is not None:
            errors.append((job["host"], error))
    return results, errors, stop_requested(), outcomes
