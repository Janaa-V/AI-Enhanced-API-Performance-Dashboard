"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from app.services.simulation import Simulator


def get_simulator(request: Request) -> Simulator:
    return request.app.state.simulator


SimulatorDep = Annotated[Simulator, Depends(get_simulator)]
