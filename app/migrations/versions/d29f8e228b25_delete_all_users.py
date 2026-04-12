"""delete_all_users

Revision ID: d29f8e228b25
Revises: 0482c9d51cc6
Create Date: 2026-04-05 20:32:23.107737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd29f8e228b25'
down_revision: Union[str, Sequence[str], None] = '0482c9d51cc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Удаляем всех пользователей
    op.execute("DELETE FROM users;")
    # Сбрасываем счётчик последовательности для id
    op.execute("ALTER SEQUENCE users_id_seq RESTART WITH 1;")

def downgrade():
    # Восстановление невозможно, можно либо ничего не делать,
    # либо вставить заглушку (например, предупреждение)
    pass