"""Shared FastAPI dependencies."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session
from app.services.simulation import Simulator

Clock = Callable[[], datetime]


def get_simulator(request: Request) -> Simulator:
    return request.app.state.simulator


SimulatorDep = Annotated[Simulator, Depends(get_simulator)]


def get_clock() -> Clock:
    """The current UTC time; tests override it to fix the metrics window."""
    return lambda: datetime.now(UTC)


ClockDep = Annotated[Clock, Depends(get_clock)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
