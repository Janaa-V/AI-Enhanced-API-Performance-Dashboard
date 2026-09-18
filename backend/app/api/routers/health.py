"""Service and PostgreSQL readiness."""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    try:
        await asyncio.wait_for(request.app.state.database.check_connection(), timeout=5)
    except (SQLAlchemyError, OSError, TimeoutError):
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok", "database": "ok"}
