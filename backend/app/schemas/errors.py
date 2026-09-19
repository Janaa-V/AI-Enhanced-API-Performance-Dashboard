"""The one JSON shape every API failure uses."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str  # short and machine-readable, for clients to branch on
    message: str  # human-readable


class ErrorResponse(BaseModel):
    error: ErrorDetail
