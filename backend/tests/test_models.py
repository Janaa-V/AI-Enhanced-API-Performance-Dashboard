"""Lock in the request_logs design decisions; no database connection is needed."""

from sqlalchemy import BigInteger, DateTime, Double, SmallInteger

from app.models import Base


def test_request_logs_columns_and_types() -> None:
    table = Base.metadata.tables["request_logs"]
    assert list(table.columns.keys()) == [
        "id",
        "endpoint",
        "method",
        "status_code",
        "latency_ms",
        "started_at",
    ]
    assert all(not column.nullable for column in table.columns)
    assert isinstance(table.c.id.type, BigInteger)
    assert isinstance(table.c.status_code.type, SmallInteger)
    assert isinstance(table.c.latency_ms.type, Double)
    assert isinstance(table.c.started_at.type, DateTime)
    assert table.c.started_at.type.timezone is True


def test_request_logs_constraints_and_index_names() -> None:
    table = Base.metadata.tables["request_logs"]
    assert {constraint.name for constraint in table.constraints} == {
        "pk_request_logs",
        "ck_request_logs_latency_non_negative",
        "ck_request_logs_status_code_range",
    }
    assert {index.name for index in table.indexes} == {"ix_request_logs_started_at"}
