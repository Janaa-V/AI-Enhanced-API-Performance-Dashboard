"""create request_logs

Revision ID: 70b1e6bc82d2
Revises:
Create Date: 2026-09-19 21:57:14.719617

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "70b1e6bc82d2"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the request_logs table and its time index."""
    op.create_table(
        "request_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("latency_ms", sa.Double(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latency_ms >= 0", name=op.f("ck_request_logs_latency_non_negative")),
        sa.CheckConstraint(
            "status_code BETWEEN 100 AND 599", name=op.f("ck_request_logs_status_code_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_logs")),
    )
    op.create_index(
        op.f("ix_request_logs_started_at"), "request_logs", ["started_at"], unique=False
    )


def downgrade() -> None:
    """Drop the request_logs table."""
    op.drop_index(op.f("ix_request_logs_started_at"), table_name="request_logs")
    op.drop_table("request_logs")
