"""Initial schema (tables created by database/init.sql on Postgres first start).

Revision ID: 001
Revises:
Create Date: Initial


"""
from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Schema is created by init.sql; no-op for Alembic."""
    pass


def downgrade() -> None:
    """No-op."""
    pass
