"""
Retry transient failures with a structured ``while`` + ``with`` session: :class:`WhileWithRetry`.

This module provides a small retry engine intended for I/O-like operations, where you want:

- a bounded number of retries,
- a clean separation between "do the work" (the ``with`` body) and "handle failures",
- explicit session state (``outcome``, ``error``, ``last_exception``),
- optional hooks (retry decision, logging/telemetry, and final failure handling).

The basic usage pattern is always::

    r = WhileWithRetry(...)
    while r:
        with r.attempt():
            ... do one attempt ...

After the loop:

- if ``r.outcome == 'ok'``: the body has completed without raising and the session is finished;
- if ``r.outcome == 'failed'``: the session ended due to an exception; ``r.error`` is set.

Retry budget / counting
----------------------

``retries`` is the number of *extra* attempts after the first try (same idea as
``range(retries + 1)``). For example, ``retries=2`` allows up to 3 total attempts.

Which exceptions are retryable
------------------------------

By default, **nothing is retryable** (``exc_retry_list`` is empty and ``on_is_retry`` is unset).
To enable retries, either:

- pass ``exc_retry_list=(SomeError, ...)`` for type-based retries, or
- pass ``on_is_retry(r, exc) -> bool`` for a custom decision function, or
- override :meth:`WhileWithRetry.is_retry` in a subclass.

If an exception is not retryable, it is recorded as failure and **propagates** out of the
``with`` block (i.e. it is not swallowed).

Hooks and control flow
----------------------

The engine calls (in order) :meth:`WhileWithRetry.proc_exception`, :meth:`WhileWithRetry.is_retry`,
and then either :meth:`WhileWithRetry.proc_retry` (retry scheduled) or
:meth:`WhileWithRetry.proc_fail` (final failure).

``on_exception(r, exc) -> bool`` is an optional early override. If it returns ``True``, the session
ends immediately as failed (``r.error`` is set) and the exception is **suppressed** by ``__exit__``.
If it returns ``False`` (or any non-``True`` value), the engine proceeds with normal retry logic.

``on_retry(r, exc)`` runs once per scheduled retry (before the inter-attempt sleep).

``on_fail(r, exc)`` runs once when the session enters the final ``outcome == 'failed'`` state.
``r.error`` is set to ``exc`` before the callback runs.

Examples
--------

Retry reading a file on ``OSError``, sleeping between attempts::

    from pathlib import Path
    from while_with_retry import WhileWithRetry

    path = Path('data.txt')
    r = WhileWithRetry(retries=2, pause_sec=1.0, exc_retry_list=(OSError,))
    text = None

    while r:
        with r.attempt():
            text = path.read_text(encoding='utf-8')

    if r.outcome != 'ok':
        raise r.error

Use ``on_is_retry`` instead of ``exc_retry_list``::

    def is_transient(r: WhileWithRetry, exc: BaseException) -> bool:
        return isinstance(exc, OSError)

    r = WhileWithRetry(retries=3, pause_sec=0.2, on_is_retry=is_transient)

Abort and suppress a specific exception via ``on_exception``::

    def stop_on_value_error(r: WhileWithRetry, exc: BaseException) -> bool:
        return isinstance(exc, ValueError)

    r = WhileWithRetry(retries=2, exc_retry_list=(OSError,), on_exception=stop_on_value_error)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class WhileWithRetry:
    """
    Coordinate ``while self:`` with ``with self.attempt():`` for bounded retries.

    See the module docstring for the full usage guide, hook semantics, and examples.

    Attributes:
        retries: How many retryable failures to swallow before ending the session as failed.
        pause_sec: Sleep duration (seconds) between retry attempts.
        exc_retry_list: Exception types that are considered retryable when ``on_is_retry`` is not set.
        on_exception: Optional hook invoked for any exception from the ``with attempt():`` body.
            If it returns ``True``, the session ends as failed and the exception is suppressed.
        on_is_retry: Optional hook that decides whether an exception is retryable.
        on_retry: Optional hook invoked before sleeping in a retry step.
        on_fail: Optional hook invoked when the session ends as failed (after ``error`` is assigned).

        outcome: Session outcome: ``'running'`` while attempts are in progress, then ``'ok'`` or ``'failed'``.
        error: Final exception that ended the session as failed (only set when ``outcome == 'failed'``).
        last_exception: Most recent exception raised by the ``with attempt():`` body.
            Useful for logging/telemetry during retries. Reset to ``None`` on success.

    Quick example::

        r = WhileWithRetry(retries=2, pause_sec=0.5, exc_retry_list=(OSError,))
        data = None
        while r:
            with r.attempt():
                with open(path, 'rb') as f:
                    data = f.read()

        if r.outcome != 'ok':
            raise r.error
    """

    retries: int
    pause_sec: float = 0.0
    exc_retry_list: tuple[type[BaseException], ...] = ()
    on_exception: Callable[['WhileWithRetry', BaseException], bool] | None = None
    on_is_retry: Callable[['WhileWithRetry', BaseException], bool] | None = None
    on_retry: Callable[['WhileWithRetry', BaseException], None] | None = None
    on_fail: Callable[['WhileWithRetry', BaseException], None] | None = None

    _failures_swallowed: int = field(default=0, init=False)
    _done: bool = field(default=False, init=False)
    outcome: str = field(default='running', init=False)
    error: BaseException | None = field(default=None, init=False)
    last_exception: BaseException | None = field(default=None, init=False)

    def __bool__(self) -> bool:
        return not self._done

    def attempt(self) -> '_AttemptCtx':
        return _AttemptCtx(self)

    def proc_exception(self, exc: BaseException) -> bool:
        """Run ``on_exception`` if set. ``True`` means end as failed and suppress the exception."""
        if self.on_exception is None:
            return False
        return self.on_exception(self, exc) is True

    def is_retry(self, exc: BaseException) -> bool:
        """Whether ``exc`` is retryable: ``on_is_retry`` if set, else ``isinstance`` against ``exc_retry_list``."""
        if self.on_is_retry is not None:
            return self.on_is_retry(self, exc)
        if not self.exc_retry_list:
            return False
        return isinstance(exc, self.exc_retry_list)

    def proc_retry(self, exc: BaseException) -> None:
        """Run ``on_retry`` if set (before ``pause_sec`` in the retry step)."""
        if self.on_retry is not None:
            self.on_retry(self, exc)

    def proc_fail(self, exc: BaseException) -> None:
        """Run ``on_fail`` if set (``error`` is already assigned)."""
        if self.on_fail is not None:
            self.on_fail(self, exc)

    def _finalize_failed(self, exc: BaseException) -> None:
        self._done = True
        self.outcome = 'failed'
        self.error = exc
        self.proc_fail(exc)

    def _apply_retry_step(self, exc: BaseException) -> bool:
        """Sleep, bump failure count; return True to retry, else set failed state and return False."""
        if self._failures_swallowed < self.retries:
            self.proc_retry(exc)
            time.sleep(self.pause_sec)
            self._failures_swallowed += 1
            return True
        self._finalize_failed(exc)
        return False


class _AttemptCtx:
    def __init__(self, r: WhileWithRetry) -> None:
        self._r = r

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        r = self._r
        if exc_type is None:
            r.last_exception = None
            r._done = True
            r.outcome = 'ok'
            r.error = None
            return False

        r.last_exception = exc

        if r.proc_exception(exc):
            r._finalize_failed(exc)
            r.last_exception = None
            return True

        retryable = r.is_retry(exc)

        if not retryable:
            r._finalize_failed(exc)
            return False

        return r._apply_retry_step(exc)
