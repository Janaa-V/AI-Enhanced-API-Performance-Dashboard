"""Saves one request_logs row per monitored request.

Recording is best effort: a failed or slow save is logged and dropped, and never
raised, so monitoring can never break or delay the API it observes.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RequestLog

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@dataclass(frozen=True, slots=True)
class RequestRecord:
    """What is known about one finished request."""

    method: str
    endpoint: str  # the route template such as /demo/orders, never the raw path
    status_code: int
    latency_ms: float  # measured with a monotonic clock
    started_at: datetime  # timezone-aware, UTC


class RequestRecorder:
    def __init__(self, sessions: SessionFactory, *, timeout_seconds: float = 2.0) -> None:
        self._sessions = sessions
        self._timeout_seconds = timeout_seconds

    async def record(self, record: RequestRecord) -> None:
        """Save the record in a short transaction; log and drop it on any failure."""
        try:
            async with asyncio.timeout(self._timeout_seconds), self._sessions() as session:
                session.add(
                    RequestLog(
                        endpoint=record.endpoint,
                        method=record.method,
                        status_code=record.status_code,
                        latency_ms=record.latency_ms,
                        started_at=record.started_at,
                    )
                )
                await session.commit()
        except Exception as error:
            # Cancellation is a BaseException, so shutdown still propagates.
            # One short line per failure: a database outage must not flood the logs
            # with tracebacks. The full traceback is available at debug level.
            logger.warning(
                "Could not record request %s %s (status %s): %s: %s",
                record.method,
                record.endpoint,
                record.status_code,
                type(error).__name__,
                str(error).splitlines()[0] if str(error) else "no details",
            )
            logger.debug("Traceback for the failed recording", exc_info=True)
