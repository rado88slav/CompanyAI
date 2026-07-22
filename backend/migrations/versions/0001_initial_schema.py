"""Create initial Company AI schema baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from typing import Union

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial schema baseline.

    No application tables exist yet. Applying this migration establishes
    Alembic schema version tracking in PostgreSQL.
    """

    pass


def downgrade() -> None:
    """Remove the initial schema baseline."""

    pass
