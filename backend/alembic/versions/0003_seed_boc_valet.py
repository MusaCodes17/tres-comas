"""seed boc_valet connection (disabled)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13 23:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_connections = sa.table(
    'connections',
    sa.column('name', sa.String),
    sa.column('kind', sa.String),
    sa.column('direction', sa.String),
    sa.column('scope', sa.Text),
    sa.column('secret_env_key', sa.String),
    sa.column('enabled', sa.Boolean),
)


def upgrade() -> None:
    # Bank of Canada Valet (D-13): FX rates, no key. Disabled until Musa switches it on (INV-7).
    op.bulk_insert(_connections, [{
        'name': 'boc_valet',
        'kind': 'market_data',
        'direction': 'outbound',
        'scope': json.dumps({
            'hosts': ['www.bankofcanada.ca'],
            'params': ['start_date', 'end_date'],
            'auth': None,
        }),
        'secret_env_key': None,
        'enabled': False,
    }])


def downgrade() -> None:
    op.execute(_connections.delete().where(_connections.c.name == 'boc_valet'))
