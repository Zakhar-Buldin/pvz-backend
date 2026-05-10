"""notifications+

Revision ID: 49e8c48e582f
Revises: cf0ee4881aa2
Create Date: 2026-05-11 00:35:00.773673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49e8c48e582f'
down_revision: Union[str, Sequence[str], None] = 'cf0ee4881aa2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute("DELETE FROM notifications")
    op.execute("ALTER SEQUENCE notifications_id_seq RESTART WITH 1")

    op.add_column(
        'notifications',
        sa.Column('problem_solution', sa.String(length=1000), nullable=True)
    )

    op.add_column(
        'notifications',
        sa.Column('solution_date', sa.Date(), nullable=True)
    )

def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column('notifications', 'solution_date')
    op.drop_column('notifications', 'problem_solution')