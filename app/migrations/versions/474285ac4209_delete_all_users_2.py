"""delete_all_users_2

Revision ID: 474285ac4209
Revises: 1109bbbf4e2b
Create Date: 2026-04-20 10:11:31.572015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '474285ac4209'
down_revision: Union[str, Sequence[str], None] = '1109bbbf4e2b'
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
