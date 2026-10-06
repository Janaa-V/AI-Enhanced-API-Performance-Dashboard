"""Turn one metrics window into an AI-assisted analysis.

Order matters:
1. Read the input in one read-only snapshot.
2. End that transaction, so no database connection waits on the slow provider call.
3. With too little traffic, answer "no_data" without calling the provider.
4. Call the provider, then reject any answer that names an endpoint not in the input.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analysis import Analysis, AnalysisResponse, AnalysisWindow
from app.services.analysis.input import AnalysisInput, collect_analysis_input
from app.services.analysis.prompt import SYSTEM_PROMPT, user_message
from app.services.analysis.providers import AnalysisProvider, ProviderError

logger = logging.getLogger(__name__)

# Below this, percentages and p95 rest on a handful of requests and say little.
MIN_REQUESTS = 20


def unknown_endpoints(answer: Analysis, data: AnalysisInput) -> list[str]:
    """Endpoints the answer names that were not in its input; null means the whole API."""
    named = {o.endpoint for o in answer.observations if o.endpoint is not None}
    return sorted(named - data.endpoint_names())


async def analyze(
    session: AsyncSession,
    provider: AnalysisProvider,
    *,
    clock: Callable[[], datetime],
    window_minutes: int,
) -> AnalysisResponse:
    data = await collect_analysis_input(session, end=clock(), window_minutes=window_minutes)
    # The snapshot only read; ending it returns the connection to the pool before the
    # provider call, which takes seconds. Otherwise a few analyses could starve the pool.
    await session.rollback()

    window = AnalysisWindow(
        start=data.window.start, end=data.window.end, window_minutes=window_minutes
    )
    if data.summary.total_requests < MIN_REQUESTS:
        return AnalysisResponse(
            status="no_data",
            window=window,
            generated_at=clock(),
            provider=None,
            model=None,
            cached=False,
            analysis=None,
        )

    message = user_message(data)
    started = time.perf_counter()
    try:
        answer = await provider.complete(system=SYSTEM_PROMPT, user=message)
    except ProviderError as error:
        # The error holds only a kind and a status, so it is safe to log.
        logger.warning(
            "AI analysis failed: %s from %s/%s after %.1f s",
            error,
            provider.name,
            provider.model,
            time.perf_counter() - started,
        )
        raise

    unknown = unknown_endpoints(answer, data)
    if unknown:
        # Fail closed: one invented endpoint means the whole answer cannot be trusted.
        logger.warning(
            "AI answer rejected: %s/%s named endpoints not in the data: %s",
            provider.name,
            provider.model,
            ", ".join(name[:100] for name in unknown),
        )
        raise ProviderError("bad_output")

    logger.info(
        "AI analysis by %s/%s: %d requests, %d characters in, %.1f s",
        provider.name,
        provider.model,
        data.summary.total_requests,
        len(message),
        time.perf_counter() - started,
    )
    return AnalysisResponse(
        status="ok",
        window=window,
        generated_at=clock(),
        provider=provider.name,
        model=provider.model,
        cached=False,
        analysis=answer,
    )
