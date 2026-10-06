"""AI-assisted analysis of a recent time window."""

import logging

from fastapi import APIRouter
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import AnalyzerDep, ClockDep, SessionDep, SettingsDep
from app.api.errors import ApiError, ServiceUnavailable, error_responses
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis.guard import AnalysisDisabled
from app.services.analysis.providers import ProviderError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])

DISABLED = "AI analysis is not configured on this server."
RATE_LIMITED = "Too many analyses right now; try again later."
UNAVAILABLE = "The AI provider could not produce an analysis; try again."


def api_error(error: ProviderError) -> ApiError:
    """One public answer per kind; the details stay in the server log."""
    if error.kind == "rate_limited":
        return ApiError(429, "rate_limited", RATE_LIMITED, retry_after=error.retry_after)
    if error.kind in ("auth", "bad_request"):
        # Not the user's fault and not transient: someone has to fix the configuration.
        logger.error("AI provider refused the request (%s); check AI_API_KEY and AI_MODEL", error)
    return ApiError(502, "ai_unavailable", UNAVAILABLE)


@router.post(
    "/analyze",
    responses=error_responses(
        [503],
        {
            429: RATE_LIMITED,
            502: UNAVAILABLE,
            503: f"{DISABLED} Also returned when the database is unavailable.",
        },
    ),
)
async def post_analyze(
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
    body: AnalysisRequest | None = None,
) -> AnalysisResponse:
    """Summarise the window's metrics with the configured AI provider.

    The server builds the input itself from aggregates; clients send only the window.
    """
    window_minutes = (body and body.window_minutes) or settings.metrics_window_minutes
    try:
        return await analyzer.run(session, clock=clock, window_minutes=window_minutes)
    except AnalysisDisabled:
        raise ApiError(503, "ai_disabled", DISABLED) from None
    except ProviderError as error:
        raise api_error(error) from None
    except (SQLAlchemyError, OSError) as error:
        logger.warning("Analysis query failed: %s", type(error).__name__)
        raise ServiceUnavailable from None
