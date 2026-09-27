"""Dashboard metrics for a recent time window."""

import logging
import math
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import ClockDep, SessionDep, SettingsDep
from app.api.errors import ServiceUnavailable, error_responses
from app.schemas.metrics import MetricsResponse
from app.services.metrics import collect_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

# One day in 5-minute buckets. Stops one request from building thousands of buckets
# (a day in 1-minute buckets is 1,440 per endpoint).
MAX_BUCKETS = 288


@router.get("/metrics", responses=error_responses([503]))
async def get_metrics(
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
    window_minutes: Annotated[
        int | None,
        Query(ge=1, le=1440, description="Window length; defaults to METRICS_WINDOW_MINUTES."),
    ] = None,
    bucket_minutes: Annotated[int, Query(ge=1, le=60)] = 5,
    recent_limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MetricsResponse:
    window_minutes = window_minutes or settings.metrics_window_minutes
    if window_minutes / bucket_minutes > MAX_BUCKETS:
        # Same shape as FastAPI's own 422, pointing at the parameter to change.
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "bucket_minutes"),
                    "msg": f"Too many buckets: window_minutes / bucket_minutes must be at "
                    f"most {MAX_BUCKETS}; use bucket_minutes of at least "
                    f"{math.ceil(window_minutes / MAX_BUCKETS)}.",
                    "input": bucket_minutes,
                }
            ]
        )
    try:
        return await collect_metrics(
            session,
            end=clock(),
            window_minutes=window_minutes,
            bucket_minutes=bucket_minutes,
            recent_limit=recent_limit,
        )
    except (SQLAlchemyError, OSError) as error:
        # One short line, as for recording failures; the client gets only the generic 503.
        logger.warning("Metrics query failed: %s", type(error).__name__)
        raise ServiceUnavailable from None
