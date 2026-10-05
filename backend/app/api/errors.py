"""One consistent JSON error format for every server failure."""

import math
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorDetail, ErrorResponse
from app.services.simulation import SimulatedFailure

ERROR_DETAILS: Mapping[int, ErrorDetail] = MappingProxyType(
    {
        500: ErrorDetail(
            code="internal_error", message="The server failed to process the request."
        ),
        503: ErrorDetail(
            code="service_unavailable", message="The service is temporarily unavailable."
        ),
        504: ErrorDetail(
            code="gateway_timeout", message="An upstream service took too long to respond."
        ),
    }
)
_GENERIC = ErrorDetail(code="server_error", message="The server could not complete the request.")


class ServiceUnavailable(Exception):
    """Something the request needs, such as the database, is unavailable: answered with a 503."""


class ApiError(Exception):
    """A failure with its own code, for when the status alone does not say what went wrong
    (503 can mean the database is down or that AI is not configured)."""

    def __init__(
        self, status_code: int, code: str, message: str, *, retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = ErrorDetail(code=code, message=message)
        self.retry_after = retry_after  # seconds; sent as a Retry-After header


def error_detail(status_code: int) -> ErrorDetail:
    return ERROR_DETAILS.get(status_code, _GENERIC)


def error_responses(
    statuses: Iterable[int], descriptions: Mapping[int, str] | None = None
) -> dict[int | str, dict[str, Any]]:
    """OpenAPI entries documenting the failures a route can return."""
    described = descriptions or {}
    return {
        status: {
            "model": ErrorResponse,
            "description": described.get(status, error_detail(status).message),
        }
        for status in sorted(set(statuses) | set(described))
    }


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(SimulatedFailure)
    async def handle_simulated_failure(
        _request: Request, failure: SimulatedFailure
    ) -> JSONResponse:
        body = ErrorResponse(error=error_detail(failure.status_code))
        return JSONResponse(status_code=failure.status_code, content=body.model_dump())

    @application.exception_handler(ServiceUnavailable)
    async def handle_service_unavailable(
        _request: Request, _error: ServiceUnavailable
    ) -> JSONResponse:
        # The generic message only: causes such as connection details stay in the server log.
        body = ErrorResponse(error=error_detail(503))
        return JSONResponse(status_code=503, content=body.model_dump())

    @application.exception_handler(ApiError)
    async def handle_api_error(_request: Request, error: ApiError) -> JSONResponse:
        headers = None
        if error.retry_after is not None:
            # Whole seconds, rounded up, so a client never retries too early.
            headers = {"Retry-After": str(max(1, math.ceil(error.retry_after)))}
        body = ErrorResponse(error=error.detail)
        return JSONResponse(
            status_code=error.status_code, content=body.model_dump(), headers=headers
        )
