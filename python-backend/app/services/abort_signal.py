"""Cooperative abort signal for agent execution.

Mirrors TS ``agentRuntime/abort.ts``.

Usage::

    signal = AbortSignal()

    # In a graph node:
    signal.throw_if_aborted("context before LLM call")

    # From outside (interrupt endpoint):
    signal.abort("User cancelled")
"""

from __future__ import annotations

import threading
from typing import Optional


class AbortError(Exception):
    """Raised when agent execution is aborted."""

    def __init__(self, message: str = "Agent execution aborted") -> None:
        super().__init__(message)
        self.name = "AbortError"


class AbortSignal:
    """Thread-safe cooperative abort signal.

    Unlike JS ``AbortSignal``, Python has no built-in equivalent, so we
    implement a simple boolean flag with a lock.
    """

    def __init__(self) -> None:
        self._aborted = False
        self._reason: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    def abort(self, reason: str = "Agent execution aborted") -> None:
        """Signal that execution should be aborted."""
        with self._lock:
            if self._aborted:
                return
            self._aborted = True
            self._reason = reason

    def throw_if_aborted(self, message: str = "Agent execution aborted") -> None:
        """Raise ``AbortError`` if the signal has been triggered."""
        if self._aborted:
            raise get_abort_error(self, message)


def create_abort_error(message: str = "Agent execution aborted") -> AbortError:
    """Create an AbortError with the given message."""
    return AbortError(message)


def get_abort_error(
    signal: Optional[AbortSignal] = None,
    message: str = "Agent execution aborted",
) -> AbortError:
    """Get an AbortError from a signal's reason, or create one."""
    if signal and signal.reason:
        return AbortError(signal.reason)
    return AbortError(message)


def throw_if_aborted(
    signal: Optional[AbortSignal] = None,
    message: str = "Agent execution aborted",
) -> None:
    """Raise AbortError if the signal has been triggered."""
    if signal and signal.aborted:
        raise get_abort_error(signal, message)


def is_abort_error(error: BaseException) -> bool:
    """Check if an error is an AbortError."""
    return isinstance(error, AbortError)
