"""
Retry transient I/O errors with a ``while`` + ``with`` session: :class:`WhileWithRetry`.

The session runs until the body inside ``with r.attempt():`` finishes without raising, or
until a non-retryable exception propagates, or until retryable exceptions exceed the
configured ``retries`` (same counting style as ``fss_utils.load_yaml``: ``retries`` is the
number of *extra* attempts after the first try).

The built-in retry path does not log; pass ``on_exception`` and handle decisions from
:meth:`WhileWithRetry.proc_exception` (internally ``on_exception(r, exc)``) if you want messages or
structured logging before returning a decision (see table below).

``on_exception(r, exc)`` must return ``True`` or ``False``. Only ``True`` is handled specially (see
table); any other return value delegates like ``False``.

| Return | Typical meaning | Session ``outcome`` | Exception escapes ``with`` |
|--------|-----------------|---------------------|------------------------------|
| ``True`` | Stop immediately as ``failed``, record ``r.error``, do not re-raise | ``failed`` | No (suppressed) |
| ``False`` | Delegate to :meth:`WhileWithRetry.is_retry` (``on_is_retry`` if set, else ``retry_on``) | Same as built-in path | Yes if not retryable or budget exhausted |

Example — read a file text, sleeping between ``OSError`` retries::

    from pathlib import Path
    from while_with_retry import WhileWithRetry

    path = Path('data.txt')
    r = WhileWithRetry(retries=2, pause_sec=1.0, retry_on=(OSError,))
    text = None
    while r:
        with r.attempt():
            text = path.read_text(encoding='utf-8')

    if r.outcome != 'ok':
        raise r.error

Non-retryable errors (e.g. :meth:`WhileWithRetry.is_retry` is ``False`` for ``exc``) are not
swallowed: they end the session with ``outcome == 'failed'`` and propagate out of ``__exit__``
after recording ``r.error``. The same end state without propagating is selected when
:meth:`WhileWithRetry.proc_exception` reports the ``on_exception`` callback returned ``True``.

Optional ``on_retry`` / ``on_fail`` are invoked from :meth:`WhileWithRetry.proc_retry` and
:meth:`WhileWithRetry.proc_fail`. ``on_retry(r)`` runs once each time the session schedules
another attempt (before the inter-attempt ``pause_sec`` sleep). Use ``r.last_exception`` inside
the callback if you need the exception instance (``on_retry`` only receives ``r``).
``on_fail(r, exc)`` runs once when the session enters the final ``outcome == 'failed'`` state
(including non-retryable errors and exhausted retry budget); ``r.error`` is set to ``exc`` before
``on_fail`` runs.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class WhileWithRetry:
    """
    Coordinate ``while self:`` with ``with self.attempt():`` for bounded I/O retries.

    ``retries`` is the number of *extra* attempts after the first try (same idea as
    ``range(retries + 1)`` in ``fss_utils.load_yaml``).

    The engine calls :meth:`proc_exception`, :meth:`is_retry`, :meth:`proc_retry`, and
    :meth:`proc_fail`; those methods forward to optional ``on_exception``, ``on_is_retry``,
    ``on_retry``, and ``on_fail`` callbacks respectively.

    ``on_exception(r, exc)`` is used from :meth:`proc_exception`; it must return ``True`` (end as
    ``failed``, suppress the exception) or ``False`` (use :meth:`is_retry` and counting). Use
    ``on_retry`` / ``on_fail`` for logging (via :meth:`proc_retry` / :meth:`proc_fail`).

    ``on_retry(r)`` runs for each scheduled retry (before ``pause_sec``). ``last_exception`` is
    the exception currently being handled (set before :meth:`proc_retry` / :meth:`proc_fail`).
    ``on_fail(r, exc)`` runs when the session ends as ``failed`` (``r.error`` is set to ``exc``
    beforehand).

    Example — same pattern as the module docstring, with explicit outcome handling::

        r = WhileWithRetry(retries=3, pause_sec=0.5, retry_on=(OSError,))
        result = None
        while r:
            with r.attempt():
                with open(path, 'rb') as f:
                    result = f.read(1024)

        if r.outcome != 'ok':
            raise r.error

    ``on_is_retry(r, exc)`` — optional functional counterpart to ``retry_on`` (if set, it replaces
    the tuple check for whether the exception is retryable). Return ``True`` to take a retry
    step (still bounded by ``retries``), ``False`` to end the session as failed and re-raise.

    Example — custom handler (abort the ``with`` body without propagating on a specific error)::

        def decide(r: WhileWithRetry, exc: BaseException) -> bool:
            if isinstance(exc, ValueError):
                return True
            return False

        r = WhileWithRetry(retries=2, pause_sec=1.0, retry_on=(OSError,), on_exception=decide)

    Example — type-based retries via ``on_is_retry`` instead of ``retry_on``::

        def is_io(r: WhileWithRetry, exc: BaseException) -> bool:
            return isinstance(exc, OSError)

        r = WhileWithRetry(retries=2, pause_sec=1.0, on_is_retry=is_io)

    Attributes updated by :meth:`attempt` / ``_AttemptCtx``:

    - ``outcome``: ``'running'`` until finished, then ``'ok'`` or ``'failed'``.
    - ``error``: set when ``outcome == 'failed'`` (last exception or non-retryable break).
    - ``last_exception``: last exception passed to ``__exit__`` while handling a failure;
      cleared when an attempt completes without raising.
    """

    retries: int
    pause_sec: float = 0.0
    retry_on: tuple[type[BaseException], ...] = (OSError,)
    on_exception: Callable[['WhileWithRetry', BaseException], bool] | None = None
    on_is_retry: Callable[['WhileWithRetry', BaseException], bool] | None = None
    on_retry: Callable[['WhileWithRetry'], None] | None = None
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
        """Whether ``exc`` is retryable: ``on_is_retry`` if set, else ``isinstance`` against ``retry_on``."""
        if self.on_is_retry is not None:
            return self.on_is_retry(self, exc)
        return isinstance(exc, self.retry_on)

    def proc_retry(self) -> None:
        """Run ``on_retry`` if set (before ``pause_sec`` in the retry step)."""
        if self.on_retry is not None:
            self.on_retry(self)

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
            self.proc_retry()
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
