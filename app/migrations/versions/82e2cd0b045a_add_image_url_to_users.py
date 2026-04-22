"""add image_url to users

Revision ID: 82e2cd0b045a
Revises: 4d0df83e70ea
Create Date: 2026-04-23 01:03:23.816494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82e2cd0b045a'
down_revision: Union[str, Sequence[str], None] = '4d0df83e70ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('users', sa.Column('image_url', sa.String(), nullable=True))

def downgrade():
    op.drop_column('users', 'image_url')