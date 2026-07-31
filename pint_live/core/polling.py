"""Shared polling control primitives."""


class PollCancelled(Exception):
    """Raised when the user requests that an in-progress poll stop."""
