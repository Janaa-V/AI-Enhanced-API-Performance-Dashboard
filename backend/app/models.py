"""Database models. Schema changes are made through Alembic migrations."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    Identity,
    MetaData,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint and index names keep Alembic migrations predictable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class RequestLog(Base):
    """One monitored request. The end time is started_at plus latency_ms."""

    __tablename__ = "request_logs"
    __table_args__ = (
        CheckConstraint("status_code BETWEEN 100 AND 599", name="status_code_range"),
        CheckConstraint("latency_ms >= 0", name="latency_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(SmallInteger)
    latency_ms: Mapped[float] = mapped_column(Double)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
