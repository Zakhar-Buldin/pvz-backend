"""Clear

Revision ID: 5fed73996b23
Revises: 40a064bae9a9
Create Date: 2026-02-23 03:10:00.574755

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fed73996b23'
down_revision: Union[str, Sequence[str], None] = '40a064bae9a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Отключаем проверку внешних ключей (на всякий случай)
    op.execute("SET CONSTRAINTS ALL DEFERRED")

    # Очищаем все таблицы (порядок может быть любым благодаря CASCADE)
    op.execute("TRUNCATE TABLE operations CASCADE;")
    op.execute("TRUNCATE TABLE delivery_items CASCADE;")
    op.execute("TRUNCATE TABLE deliveries CASCADE;")
    op.execute("TRUNCATE TABLE products CASCADE;")
    op.execute("TRUNCATE TABLE pvz CASCADE;")

    # Сбрасываем автоинкрементные счётчики (опционально)
    op.execute("ALTER SEQUENCE operations_id_seq RESTART WITH 1;")
    op.execute("ALTER SEQUENCE delivery_items_id_seq RESTART WITH 1;")
    op.execute("ALTER SEQUENCE deliveries_id_seq RESTART WITH 1;")
    op.execute("ALTER SEQUENCE products_id_seq RESTART WITH 1;")
    op.execute("ALTER SEQUENCE pvz_id_seq RESTART WITH 1;")

    # Включаем проверку обратно
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")


def downgrade():
    # В downgrade мы не можем восстановить данные, поэтому ничего не делаем
    # или можно поднять исключение, чтобы предотвратить откат
    pass