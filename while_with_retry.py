"""
Retry transient I/O errors with a ``while`` + ``with`` session: :class:`WhileWithRetry`.

The session runs until the body inside ``with r.attempt():`` finishes without raising, or
until a non-retryable exception propagates, or until retryable exceptions exceed the
configured ``retries`` (same counting style as ``fss_utils.load_yaml``: ``retries`` is the
number of *extra* attempts after the first try).

The built-in retry path does not log; use ``on_exception`` if you want messages or
structured logging before returning ``True`` / ``False`` / ``None``.

Optional ``on_exception(exc) -> False | True | None`` overrides per exception: ``False``
stops all further attempts, ``True`` forces a retry step (still bounded by ``retries``),
``None`` falls back to ``retry_on`` (see :class:`WhileWithRetry`).

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

Non-retryable errors (e.g. ``FileNotFoundError`` if not a subclass of ``retry_on``) are
not swallowed: they end the session with ``outcome == 'failed'`` and propagate out of
``__exit__`` after recording ``r.error``.
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

    Optional ``on_exception`` is called for every exception raised by the ``with`` body.
    There is no built-in ``print``; use this hook for logging if you need it. Return value:

    - ``False`` — stop the session immediately (no further attempts), set ``outcome`` to
      ``'failed'``, store the exception in ``error``, and re-raise it out of ``__exit__``.
    - ``True`` — take one retry step: same sleep and counter as the built-in path; if the
      retry budget is exhausted, behave like a final failure (``outcome == 'failed'``,
      exception propagates).
    - ``None`` — ignore the handler for this decision and use ``retry_on`` plus ``retries``
      exactly like when ``on_exception`` was not passed.

    Example — same pattern as the module docstring, with explicit outcome handling::

        r = WhileWithRetry(retries=3, pause_sec=0.5, retry_on=(OSError,))
        result = None
        while r:
            with r.attempt():
                with open(path, 'rb') as f:
                    result = f.read(1024)

        if r.outcome != 'ok':
            raise r.error

    Example — custom handler (log or filter; retry only a specific errno, else delegate with ``None``)::

        import logging

        def decide(exc: BaseException) -> bool | None:
            if isinstance(exc, OSError) and exc.errno == 11:
                logging.warning('retry after errno 11: %s', exc)
                return True
            return None

        r = WhileWithRetry(retries=2, pause_sec=1.0, retry_on=(OSError,), on_exception=decide)

    Attributes updated by :meth:`attempt` / ``_AttemptCtx``:

    - ``outcome``: ``'running'`` until finished, then ``'ok'`` or ``'failed'``.
    - ``error``: set when ``outcome == 'failed'`` (last exception or non-retryable break).
    """

    retries: int
    pause_sec: float = 0.0
    retry_on: tuple[type[BaseException], ...] = (OSError,)
    on_exception: Callable[[BaseException], bool | None] | None = None

    _failures_swallowed: int = field(default=0, init=False)
    _done: bool = field(default=False, init=False)
    outcome: str = field(default='running', init=False)
    error: BaseException | None = field(default=None, init=False)

    def __bool__(self) -> bool:
        return not self._done

    def attempt(self) -> '_AttemptCtx':
        return _AttemptCtx(self)

    def _apply_retry_step(self, exc: BaseException) -> bool:
        """Sleep, bump failure count; return True to retry, else set failed state and return False."""
        if self._failures_swallowed < self.retries:
            time.sleep(self.pause_sec)
            self._failures_swallowed += 1
            return True
        self._done = True
        self.outcome = 'failed'
        self.error = exc
        return False


class _AttemptCtx:
    def __init__(self, r: WhileWithRetry) -> None:
        self._r = r

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        r = self._r
        if exc_type is None:
            r._done = True
            r.outcome = 'ok'
            r.error = None
            return False

        if r.on_exception is not None:
            decision = r.on_exception(exc)
            if decision is False:
                r._done = True
                r.outcome = 'failed'
                r.error = exc
                return False
            if decision is True:
                return r._apply_retry_step(exc)

        if not issubclass(exc_type, r.retry_on):
            r._done = True
            r.outcome = 'failed'
            r.error = exc
            return False

        return r._apply_retry_step(exc)
