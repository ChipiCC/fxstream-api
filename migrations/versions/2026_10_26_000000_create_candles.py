"""replace the template items table with candles

Hand-written native SQL (no ORM autogeneration).

Revision ID: 2026_10_26_000000
Revises: 2026_01_01_000000
Create Date: 2026-10-26 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2026_10_26_000000"
down_revision: str | None = "2026_01_01_000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS items")
    op.execute(
        """
        CREATE TABLE candles (
            symbol TEXT NOT NULL,
            interval_code TEXT NOT NULL,
            open_time TIMESTAMPTZ NOT NULL,
            open_price NUMERIC(30, 12) NOT NULL,
            high_price NUMERIC(30, 12) NOT NULL,
            low_price NUMERIC(30, 12) NOT NULL,
            close_price NUMERIC(30, 12) NOT NULL,
            volume NUMERIC(38, 12),
            PRIMARY KEY (symbol, interval_code, open_time)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_candles_lookup
        ON candles (symbol, interval_code, open_time DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE candles")
    op.execute(
        """
        CREATE TABLE items (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id)
        )
        """
    )
    op.execute("CREATE INDEX ix_items_name ON items (name)")
