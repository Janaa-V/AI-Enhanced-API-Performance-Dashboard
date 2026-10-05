"""Protection around the analysis service: a short cache, one call per window, and a quota.

Free-tier quota is the scarce resource, so:
- the same window within AI_CACHE_SECONDS reuses the last answer (marked `cached`);
- callers asking for the same window at once wait for one call instead of making their own;
- at most AI_QUOTA_PER_HOUR real provider calls happen in any rolling hour, across all
  clients. Cached and "no_data" answers never reach the provider, so they cost nothing.

All state lives in this process, which fits the single backend instance. With several
instances, the cache, locks and quota would move to a shared store such as Redis.
"""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.schemas.analysis import Analysis, AnalysisResponse
from app.services.analysis.providers import AnalysisProvider, ProviderError, build_provider
from app.services.analysis.service import analyze

QUOTA_PERIOD_SECONDS = 3600.0


class AnalysisDisabled(Exception):
    """No AI provider is configured on this server."""


@dataclass(slots=True)
class QuotaProvider:
    """A provider that allows at most `limit` calls in any rolling hour.

    A call counts as soon as it starts, even if it then fails: the provider has still
    spent the request against our account.
    """

    inner: AnalysisProvider
    limit: int
    monotonic: Callable[[], float] = time.monotonic
    started: deque[float] = field(default_factory=deque)

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    async def complete(self, *, system: str, user: str) -> Analysis:
        now = self.monotonic()
        while self.started and now - self.started[0] >= QUOTA_PERIOD_SECONDS:
            self.started.popleft()
        if len(self.started) >= self.limit:
            # The oldest call leaves the rolling hour first.
            wait = QUOTA_PERIOD_SECONDS - (now - self.started[0])
            raise ProviderError("rate_limited", retry_after=wait)
        self.started.append(now)
        return await self.inner.complete(system=system, user=user)


@dataclass(slots=True)
class Analyzer:
    provider: AnalysisProvider | None  # None when AI is disabled
    cache_seconds: float
    monotonic: Callable[[], float] = time.monotonic
    # Keyed by window length; at most 1,440 keys, since windows are 1-1440 minutes.
    answers: dict[int, tuple[float, AnalysisResponse]] = field(default_factory=dict)
    locks: defaultdict[int, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))

    def cached(self, window_minutes: int) -> AnalysisResponse | None:
        entry = self.answers.get(window_minutes)
        if entry is None or self.monotonic() >= entry[0]:
            return None
        # Same answer and original generation time; only the flag says it is reused.
        return entry[1].model_copy(update={"cached": True})

    async def run(
        self,
        session: AsyncSession,
        *,
        clock: Callable[[], datetime],
        window_minutes: int,
    ) -> AnalysisResponse:
        if self.provider is None:
            raise AnalysisDisabled
        # One call per window at a time. Waiters hold no database connection: the session
        # starts its transaction only when analyze() runs its first query.
        async with self.locks[window_minutes]:
            # A fresh answer, often stored by whoever held the lock just before us.
            if (hit := self.cached(window_minutes)) is not None:
                return hit
            result = await analyze(
                session, self.provider, clock=clock, window_minutes=window_minutes
            )
            # Errors raise above, so they are never stored. With a cache time of 0 the entry
            # is already expired, so it is never served.
            self.answers[window_minutes] = (self.monotonic() + self.cache_seconds, result)
            return result


def build_analyzer(settings: Settings, client: httpx2.AsyncClient) -> Analyzer:
    provider = build_provider(settings, client)
    return Analyzer(
        provider=QuotaProvider(provider, settings.ai_quota_per_hour) if provider else None,
        cache_seconds=settings.ai_cache_seconds,
    )
