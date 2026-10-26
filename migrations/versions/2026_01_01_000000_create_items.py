"""create items table

Hand-written native SQL (no ORM autogeneration).

Revision ID: 2026_01_01_000000
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2026_01_01_000000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP TABLE items")
