"""One consistent JSON error format for every server failure."""

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


def error_detail(status_code: int) -> ErrorDetail:
    return ERROR_DETAILS.get(status_code, _GENERIC)


def error_responses(statuses: Iterable[int]) -> dict[int | str, dict[str, Any]]:
    """OpenAPI entries documenting the failures a route can return."""
    return {
        status: {"model": ErrorResponse, "description": error_detail(status).message}
        for status in sorted(set(statuses))
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
