"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-13 21:32:15.208135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models.types import DecimalText


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('accounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nickname', sa.String(length=64), nullable=False),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('base_currency', sa.String(length=3), server_default='CAD', nullable=False),
    sa.Column('broker_label', sa.String(length=64), nullable=True),
    sa.Column('last_reconciled_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("type IN ('tfsa', 'rrsp', 'non_registered', 'cash')", name='ck_accounts_type'),
    sa.CheckConstraint('length(base_currency) = 3 AND base_currency = upper(base_currency)', name='ck_accounts_base_currency'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nickname')
    )
    op.create_table('connections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('direction', sa.String(length=16), nullable=False),
    sa.Column('scope', sa.Text(), nullable=False),
    sa.Column('secret_env_key', sa.String(length=64), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("(kind = 'mcp_client' AND direction = 'inbound') OR (kind != 'mcp_client' AND direction = 'outbound')", name='ck_connections_kind_direction'),
    sa.CheckConstraint("direction IN ('outbound', 'inbound')", name='ck_connections_direction'),
    sa.CheckConstraint("kind IN ('market_data', 'news', 'llm', 'mcp_client')", name='ck_connections_kind'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('fx_rates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pair', sa.String(length=7), nullable=False),
    sa.Column('rate_date', sa.Date(), nullable=False),
    sa.Column('rate', DecimalText(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.CheckConstraint("pair GLOB '[A-Z][A-Z][A-Z]_[A-Z][A-Z][A-Z]'", name='ck_fx_rates_pair_format'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pair', 'rate_date', 'provider', name='uq_fx_rates_pair_date_provider')
    )
    op.create_table('proposals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('payload', sa.Text(), nullable=False),
    sa.Column('origin', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("status IN ('pending', 'confirmed', 'dismissed')", name='ck_proposals_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('securities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=16), nullable=False),
    sa.Column('exchange', sa.String(length=16), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('sector', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("kind IN ('stock', 'etf', 'cash')", name='ck_securities_kind'),
    sa.CheckConstraint('length(currency) = 3 AND currency = upper(currency)', name='ck_securities_currency_iso4217'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ticker', 'exchange', name='uq_securities_ticker_exchange')
    )
    op.create_table('etf_constituents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('etf_security_id', sa.Integer(), nullable=False),
    sa.Column('underlying_security_id', sa.Integer(), nullable=False),
    sa.Column('weight', DecimalText(), nullable=False),
    sa.Column('as_of_date', sa.Date(), nullable=False),
    sa.CheckConstraint('etf_security_id != underlying_security_id', name='ck_etf_constituents_not_self'),
    sa.ForeignKeyConstraint(['etf_security_id'], ['securities.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['underlying_security_id'], ['securities.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('etf_security_id', 'underlying_security_id', 'as_of_date', name='uq_etf_constituents_etf_underlying_date')
    )
    op.create_table('import_batches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('adapter', sa.String(length=32), nullable=False),
    sa.Column('file_kind', sa.String(length=16), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('rows_parsed', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_new', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_duplicate', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_rejected', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("file_kind IN ('activity', 'holdings')", name='ck_import_batches_file_kind'),
    sa.CheckConstraint("status IN ('pending', 'imported', 'failed')", name='ck_import_batches_status'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('file_hash')
    )
    op.create_table('outbound_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('connection_id', sa.Integer(), nullable=False),
    sa.Column('called_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('endpoint', sa.String(length=256), nullable=False),
    sa.Column('tickers_sent', sa.Text(), server_default='[]', nullable=False),
    sa.Column('succeeded', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('prices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('security_id', sa.Integer(), nullable=False),
    sa.Column('price_date', sa.Date(), nullable=False),
    sa.Column('close', DecimalText(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.CheckConstraint('length(currency) = 3 AND currency = upper(currency)', name='ck_prices_currency_iso4217'),
    sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('security_id', 'price_date', 'provider', name='uq_prices_security_date_provider')
    )
    op.create_table('transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('security_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('quantity', DecimalText(), nullable=True),
    sa.Column('price', DecimalText(), nullable=True),
    sa.Column('amount', DecimalText(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('split_ratio', DecimalText(), nullable=True),
    sa.Column('trade_date', sa.Date(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('import_batch_id', sa.Integer(), nullable=True),
    sa.Column('proposal_id', sa.Integer(), nullable=True),
    sa.Column('natural_key', sa.String(length=64), nullable=True),
    sa.Column('voided_at', sa.DateTime(), nullable=True),
    sa.Column('replaces_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("source IN ('manual', 'import', 'proposal')", name='ck_transactions_source'),
    sa.CheckConstraint("type IN ('buy', 'sell', 'dividend', 'deposit', 'withdrawal', 'fee', 'split', 'transfer_in', 'transfer_out')", name='ck_transactions_type'),
    sa.CheckConstraint('length(currency) = 3 AND currency = upper(currency)', name='ck_transactions_currency_iso4217'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['replaces_id'], ['transactions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('natural_key')
    )

    # INV-2: the database itself refuses to delete or rewrite ledger rows.
    op.execute(
        """
        CREATE TRIGGER transactions_no_delete
        BEFORE DELETE ON transactions
        BEGIN
            SELECT RAISE(ABORT, 'transactions are append-only (INV-2): void and replace instead');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER transactions_no_update
        BEFORE UPDATE ON transactions
        WHEN OLD.voided_at IS NOT NULL
            OR OLD.id IS NOT NEW.id
            OR OLD.account_id IS NOT NEW.account_id
            OR OLD.security_id IS NOT NEW.security_id
            OR OLD.type IS NOT NEW.type
            OR OLD.quantity IS NOT NEW.quantity
            OR OLD.price IS NOT NEW.price
            OR OLD.amount IS NOT NEW.amount
            OR OLD.currency IS NOT NEW.currency
            OR OLD.split_ratio IS NOT NEW.split_ratio
            OR OLD.trade_date IS NOT NEW.trade_date
            OR OLD.source IS NOT NEW.source
            OR OLD.import_batch_id IS NOT NEW.import_batch_id
            OR OLD.proposal_id IS NOT NEW.proposal_id
            OR OLD.natural_key IS NOT NEW.natural_key
            OR OLD.replaces_id IS NOT NEW.replaces_id
            OR OLD.note IS NOT NEW.note
            OR OLD.created_at IS NOT NEW.created_at
        BEGIN
            SELECT RAISE(ABORT, 'transactions are append-only (INV-2): only voided_at may be set, once');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS transactions_no_update")
    op.execute("DROP TRIGGER IF EXISTS transactions_no_delete")
    op.drop_table('transactions')
    op.drop_table('prices')
    op.drop_table('outbound_logs')
    op.drop_table('import_batches')
    op.drop_table('etf_constituents')
    op.drop_table('securities')
    op.drop_table('proposals')
    op.drop_table('fx_rates')
    op.drop_table('connections')
    op.drop_table('accounts')
