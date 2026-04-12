"""delete_all_users1

Revision ID: 1109bbbf4e2b
Revises: d29f8e228b25
Create Date: 2026-04-05 20:45:57.257176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1109bbbf4e2b'
down_revision: Union[str, Sequence[str], None] = 'd29f8e228b25'
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