"""Quota, cache and single-flight around the analysis service, without a database."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest

from app.config import Settings
from app.schemas.analysis import AnalysisResponse
from app.services.analysis import guard
from app.services.analysis.guard import (
    AnalysisDisabled,
    Analyzer,
    QuotaProvider,
    build_analyzer,
)
from app.services.analysis.providers import FakeProvider, ProviderError
from tests.doubles import FakeClock

NOW = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
HOUR = 3600.0


def response(status: str = "ok", window_minutes: int = 60) -> AnalysisResponse:
    produced = status == "ok"
    return AnalysisResponse.model_validate(
        {
            "status": status,
            "window": {"start": NOW, "end": NOW, "window_minutes": window_minutes},
            "generated_at": NOW,
            "provider": "fake" if produced else None,
            "model": "fake" if produced else None,
            "cached": False,
            "analysis": (
                {"headline": "Fine.", "observations": [], "hypotheses": [], "next_steps": []}
                if produced
                else None
            ),
        }
    )


# --- quota ---------------------------------------------------------------------------


async def ask(provider: QuotaProvider) -> None:
    await provider.complete(system="s", user="u")


async def test_the_quota_allows_the_limit_then_says_when_to_retry() -> None:
    clock = FakeClock()
    quota = QuotaProvider(FakeProvider(), limit=2, monotonic=clock)
    await ask(quota)
    clock.advance(600)
    await ask(quota)
    clock.advance(600)
    with pytest.raises(ProviderError) as caught:
        await ask(quota)
    assert caught.value.kind == "rate_limited"
    assert caught.value.retry_after == pytest.approx(HOUR - 1200)  # until the first call ages out


async def test_calls_leave_the_quota_after_exactly_an_hour() -> None:
    clock = FakeClock()
    quota = QuotaProvider(FakeProvider(), limit=1, monotonic=clock)
    await ask(quota)
    clock.advance(HOUR - 1)
    with pytest.raises(ProviderError):
        await ask(quota)
    clock.advance(1)
    await ask(quota)  # the first call is now an hour old


async def test_a_failed_call_still_counts() -> None:
    inner = FakeProvider(error=ProviderError("timeout"))
    quota = QuotaProvider(inner, limit=1, monotonic=FakeClock())
    with pytest.raises(ProviderError):
        await ask(quota)
    inner.error = None
    with pytest.raises(ProviderError) as caught:
        await ask(quota)
    assert caught.value.kind == "rate_limited"
    assert len(inner.calls) == 1  # the refused call never reached the provider


def test_the_quota_reports_the_real_provider() -> None:
    quota = QuotaProvider(FakeProvider(name="groq", model="m"), limit=1)
    assert (quota.name, quota.model) == ("groq", "m")


# --- cache and single-flight ----------------------------------------------------------


class Analyses:
    """Stands in for analyze(); counts calls and can block, fail or return no_data."""

    def __init__(self) -> None:
        self.windows: list[int] = []
        self.gate: asyncio.Event | None = None
        self.blocked: set[int] = set()  # windows that wait for the gate; empty means all
        self.error: Exception | None = None
        self.status = "ok"

    async def __call__(self, session: Any, provider: Any, *, clock: Any, window_minutes: int):
        self.windows.append(window_minutes)
        if self.gate is not None and (not self.blocked or window_minutes in self.blocked):
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return response(self.status, window_minutes)


@pytest.fixture
def analyses(monkeypatch: pytest.MonkeyPatch) -> Analyses:
    fake = Analyses()
    monkeypatch.setattr(guard, "analyze", fake)
    return fake


def analyzer(clock: FakeClock, cache_seconds: float = 60) -> Analyzer:
    return Analyzer(provider=FakeProvider(), cache_seconds=cache_seconds, monotonic=clock)


async def run(target: Analyzer, window_minutes: int = 60) -> AnalysisResponse:
    return await target.run(None, clock=lambda: NOW, window_minutes=window_minutes)  # type: ignore[arg-type]


async def test_without_a_provider_nothing_runs(analyses: Analyses) -> None:
    with pytest.raises(AnalysisDisabled):
        await Analyzer(provider=None, cache_seconds=60).run(
            None,  # type: ignore[arg-type]
            clock=lambda: NOW,
            window_minutes=60,
        )
    assert analyses.windows == []


async def test_a_repeat_within_the_cache_time_reuses_the_answer(analyses: Analyses) -> None:
    clock = FakeClock()
    target = analyzer(clock)
    first = await run(target)
    clock.advance(59)
    second = await run(target)
    assert analyses.windows == [60]
    assert (first.cached, second.cached) == (False, True)
    assert second.generated_at == first.generated_at  # when it was really produced
    assert second.model_dump(exclude={"cached"}) == first.model_dump(exclude={"cached"})


async def test_an_expired_answer_is_produced_again(analyses: Analyses) -> None:
    clock = FakeClock()
    target = analyzer(clock)
    await run(target)
    clock.advance(60)
    assert (await run(target)).cached is False
    assert analyses.windows == [60, 60]


async def test_each_window_has_its_own_answer(analyses: Analyses) -> None:
    target = analyzer(FakeClock())
    await run(target, 60)
    assert (await run(target, 15)).cached is False
    assert analyses.windows == [60, 15]


async def test_a_zero_cache_time_never_reuses(analyses: Analyses) -> None:
    target = analyzer(FakeClock(), cache_seconds=0)
    await run(target)
    assert (await run(target)).cached is False
    assert analyses.windows == [60, 60]


async def test_no_data_answers_are_reused_too(analyses: Analyses) -> None:
    analyses.status = "no_data"
    target = analyzer(FakeClock())
    await run(target)
    assert (await run(target)).cached is True
    assert analyses.windows == [60]


async def test_errors_are_never_reused(analyses: Analyses) -> None:
    target = analyzer(FakeClock())
    analyses.error = ProviderError("timeout")
    with pytest.raises(ProviderError):
        await run(target)
    analyses.error = None
    assert (await run(target)).cached is False
    assert analyses.windows == [60, 60]


async def test_callers_for_the_same_window_share_one_call(analyses: Analyses) -> None:
    analyses.gate = asyncio.Event()
    target = analyzer(FakeClock())
    first = asyncio.create_task(run(target))
    second = asyncio.create_task(run(target))
    await asyncio.sleep(0)
    analyses.gate.set()
    results = await asyncio.gather(first, second)
    assert analyses.windows == [60]
    assert sorted(result.cached for result in results) == [False, True]


async def test_a_slow_window_does_not_block_another(analyses: Analyses) -> None:
    analyses.gate, analyses.blocked = asyncio.Event(), {60}
    target = analyzer(FakeClock())
    slow = asyncio.create_task(run(target, 60))
    await asyncio.sleep(0)  # the 60-minute call is now stuck inside its lock
    other = await asyncio.wait_for(run(target, 15), timeout=1)
    assert other.window.window_minutes == 15 and not slow.done()
    analyses.gate.set()
    await slow


# --- built from settings --------------------------------------------------------------


async def test_the_analyzer_is_built_from_settings() -> None:
    async with httpx2.AsyncClient() as client:
        disabled = build_analyzer(Settings(_env_file=None), client)
        fake = build_analyzer(
            Settings(_env_file=None, ai_provider="fake", ai_quota_per_hour=5, ai_cache_seconds=30),
            client,
        )
    assert disabled.provider is None
    assert isinstance(fake.provider, QuotaProvider)
    assert isinstance(fake.provider.inner, FakeProvider)
    assert (fake.provider.limit, fake.cache_seconds) == (5, 30)
