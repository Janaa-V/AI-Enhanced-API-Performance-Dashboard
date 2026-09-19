"""Pure ASGI middleware that records one row per monitored request.

Rules (see the backend README):

- Only HTTP requests under the monitored prefix are recorded.
- The endpoint is the matched route template, never the raw path or query string.
  Requests that matched no route (404s) are skipped.
- Latency ends when the final response chunk is sent, so the later database write
  never counts. Normal requests are saved after the response has been sent.
- An unhandled crash is recorded as a 500 and re-raised. It is saved in a
  background task, because waiting here would delay the outer layer's 500 response.
- A client that disconnects, or a cancelled request, is not recorded.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.request_recorder import RequestRecord

logger = logging.getLogger(__name__)

MONITORED_PREFIX = "/demo/"


class Recorder(Protocol):
    async def record(self, record: RequestRecord) -> None: ...


RecorderProvider = Callable[[Scope], Recorder | None]


def route_template(scope: Scope) -> str | None:
    """The matched route's path template, such as /demo/items/{item_id}, if any."""
    return getattr(scope.get("route"), "path", None)


class RequestLoggingMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        get_recorder: RecorderProvider,
        *,
        prefix: str = MONITORED_PREFIX,
        clock: Callable[[], float] = time.perf_counter,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._app = app
        self._get_recorder = get_recorder
        self._prefix = prefix
        self._clock = clock
        self._now = now
        # Strong references, so background saves are not garbage collected mid-flight.
        self._background: set[asyncio.Task[None]] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        recorder = self._get_recorder(scope) if self._is_monitored(scope) else None
        if recorder is None:
            await self._app(scope, receive, send)
            return

        started_at = self._now()
        start = self._clock()
        status: int | None = None
        finished: float | None = None

        async def send_and_watch(message: Message) -> None:
            nonlocal status, finished
            await send(message)
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                finished = self._clock()  # the last chunk sent marks the end of the response

        try:
            await self._app(scope, receive, send_and_watch)
        except ClientDisconnect:
            raise  # nobody is waiting for an answer, so there is nothing to record
        except Exception:
            self._save_in_background(recorder, scope, started_at, self._clock() - start, 500)
            raise

        if status is not None:
            end = finished if finished is not None else self._clock()
            await self._save(recorder, scope, started_at, end - start, status)

    def _is_monitored(self, scope: Scope) -> bool:
        return scope["type"] == "http" and scope["path"].startswith(self._prefix)

    def _save_in_background(
        self, recorder: Recorder, scope: Scope, started_at: datetime, seconds: float, status: int
    ) -> None:
        task = asyncio.create_task(self._save(recorder, scope, started_at, seconds, status))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _save(
        self, recorder: Recorder, scope: Scope, started_at: datetime, seconds: float, status: int
    ) -> None:
        """Hand the record to the recorder. Never raises: monitoring must not break requests."""
        endpoint = route_template(scope)
        if endpoint is None:
            return
        try:
            await recorder.record(
                RequestRecord(
                    method=scope["method"],
                    endpoint=endpoint,
                    status_code=status,
                    latency_ms=seconds * 1000,
                    started_at=started_at,
                )
            )
        except Exception as error:
            logger.warning("Request recorder failed: %s: %s", type(error).__name__, error)
