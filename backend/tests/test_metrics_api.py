"""GET /metrics without a database: parameter checks and database failures."""

import logging

import pytest
from sqlalchemy.exc import OperationalError

from app.database import get_session
from tests.doubles import MakeClient

SECRET = "hunter2"


class BrokenSession:
    """A session whose database is gone; the error text carries connection details."""

    async def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError(
            "SELECT 1", {}, Exception(f"connection to db.internal password={SECRET} failed")
        )


@pytest.fixture
def client(make_client: MakeClient):
    test_client, _ = make_client()
    test_client.app.dependency_overrides[get_session] = lambda: BrokenSession()  # type: ignore[attr-defined]
    return test_client


@pytest.mark.parametrize(
    "query",
    [
        "window_minutes=0",
        "window_minutes=1441&bucket_minutes=60",  # 25 buckets, so only the window limit applies
        "bucket_minutes=0",
        "bucket_minutes=61",
        "recent_limit=0",
        "recent_limit=101",
        "window_minutes=ten",
    ],
)
def test_out_of_range_parameters_are_rejected(client, query: str) -> None:
    assert client.get(f"/metrics?{query}").status_code == 422


def test_too_many_buckets_is_rejected_with_a_hint_rounded_up(client) -> None:
    """1000 minutes in 3-minute buckets is 334 buckets; 1000 / 288 = 3.47, so the hint says 4."""
    response = client.get("/metrics?window_minutes=1000&bucket_minutes=3")
    assert response.status_code == 422
    (detail,) = response.json()["detail"]
    assert detail["loc"] == ["query", "bucket_minutes"]
    assert "at least 4" in detail["msg"]


def test_a_database_failure_returns_the_shared_503_without_details(
    client, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        response = client.get("/metrics")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "The service is temporarily unavailable.",
        }
    }
    assert SECRET not in response.text
    assert SECRET not in caplog.text
    assert "Metrics query failed: OperationalError" in caplog.text
