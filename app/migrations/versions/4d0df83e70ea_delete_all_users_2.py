"""delete_all_users_2

Revision ID: 4d0df83e70ea
Revises: 187eb085a186
Create Date: 2026-04-23 00:36:40.784679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d0df83e70ea'
down_revision: Union[str, Sequence[str], None] = '187eb085a186'
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
