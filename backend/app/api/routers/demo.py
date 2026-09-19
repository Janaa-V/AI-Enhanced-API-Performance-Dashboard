"""Simulated backend services.

Each handler runs only after FastAPI has validated the request, then calls the
simulator, so invalid input is rejected immediately instead of being delayed or
turned into a simulated server failure.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import SimulatorDep
from app.api.errors import error_responses
from app.schemas.demo import (
    OrdersResponse,
    ProductsResponse,
    ReportResponse,
    SearchResponse,
    UsersResponse,
)
from app.services.demo_data import (
    DEMO_ORDERS,
    DEMO_PRODUCTS,
    DEMO_REPORT,
    DEMO_USERS,
    search_products,
)
from app.services.simulation import DEFAULT_PROFILES

router = APIRouter(prefix="/demo", tags=["demo"])

# Looked up once, so a wrong name fails when the app loads, not on a request.
USERS = DEFAULT_PROFILES["users"]
PRODUCTS = DEFAULT_PROFILES["products"]
ORDERS = DEFAULT_PROFILES["orders"]
SEARCH = DEFAULT_PROFILES["search"]
REPORTS = DEFAULT_PROFILES["reports"]


@router.get("/users", responses=error_responses(USERS.failure_statuses))
async def list_users(simulator: SimulatorDep) -> UsersResponse:
    await simulator.simulate(USERS)
    return UsersResponse(users=list(DEMO_USERS))


@router.get("/products", responses=error_responses(PRODUCTS.failure_statuses))
async def list_products(simulator: SimulatorDep) -> ProductsResponse:
    await simulator.simulate(PRODUCTS)
    return ProductsResponse(products=list(DEMO_PRODUCTS))


@router.get("/orders", responses=error_responses(ORDERS.failure_statuses))
async def list_orders(simulator: SimulatorDep) -> OrdersResponse:
    await simulator.simulate(ORDERS)
    return OrdersResponse(orders=list(DEMO_ORDERS))


@router.get("/search", responses=error_responses(SEARCH.failure_statuses))
async def search(
    simulator: SimulatorDep, q: Annotated[str, Query(max_length=100)] = ""
) -> SearchResponse:
    await simulator.simulate(SEARCH)
    results = search_products(q)
    return SearchResponse(query=q, total=len(results), results=results)


@router.get("/reports", responses=error_responses(REPORTS.failure_statuses))
async def get_report(simulator: SimulatorDep) -> ReportResponse:
    await simulator.simulate(REPORTS)
    return DEMO_REPORT
