"""name_users

Revision ID: 187eb085a186
Revises: 474285ac4209
Create Date: 2026-04-20 10:22:50.506666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '187eb085a186'
down_revision: Union[str, Sequence[str], None] = '474285ac4209'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('users', sa.Column('name', sa.String(), nullable=False))

def downgrade():
    op.drop_column('users', 'name')