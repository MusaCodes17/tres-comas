"""The ten v1 ORM models (docs/architecture.md §4).

Job: declare the schema. No logic lives here; domain rules belong in services/.

Invariants upheld: INV-2 (transactions are the truth, no positions table),
INV-8 (accounts carry nicknames, never account numbers), INV-9 (every money,
quantity, rate and weight column is ``DecimalText``, with an explicit currency).
Enums are String columns with named CheckConstraints.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import DecimalText


def _currency_check(table: str, col: str = "currency") -> CheckConstraint:
    return CheckConstraint(
        f"length({col}) = 3 AND {col} = upper({col})", name=f"ck_{table}_{col}_iso4217"
    )


def _enum_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    listed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{col} IN ({listed})", name=name)


class Account(Base):
    """An investment account (TFSA, RRSP, ...) identified by a nickname.

    INV-8: there is deliberately NO account-number column; only a nickname and
    a broker label are stored.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        _enum_check("type", ("tfsa", "rrsp", "non_registered", "cash"), "ck_accounts_type"),
        CheckConstraint(
            "length(base_currency) = 3 AND base_currency = upper(base_currency)",
            name="ck_accounts_base_currency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="CAD", server_default="CAD"
    )
    broker_label: Mapped[str | None] = mapped_column(String(64))
    last_reconciled_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Security(Base):
    """A tradable instrument. Identity is ticker + exchange, never ticker alone."""

    __tablename__ = "securities"
    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_securities_ticker_exchange"),
        _currency_check("securities"),
        _enum_check("kind", ("stock", "etf", "cash"), "ck_securities_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)  # TSX, NASDAQ, NYSE
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    sector: Mapped[str | None] = mapped_column(String(64))  # for F4 sector exposure
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class ImportBatch(Base):
    """One uploaded broker file. ``file_hash`` (sha256 hex) makes re-upload idempotent."""

    __tablename__ = "import_batches"
    __table_args__ = (
        _enum_check("file_kind", ("activity", "holdings"), "ck_import_batches_file_kind"),
        _enum_check("status", ("pending", "imported", "failed"), "ck_import_batches_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    adapter: Mapped[str] = mapped_column(String(32), nullable=False)
    file_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    rows_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rows_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rows_duplicate: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rows_rejected: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Proposal(Base):
    """A transaction proposal from an external client (INV-6).

    Becomes a transaction only when Musa confirms it in the app.
    """

    __tablename__ = "proposals"
    __table_args__ = (
        _enum_check("status", ("pending", "confirmed", "dismissed"), "ck_proposals_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    origin: Mapped[str] = mapped_column(String(64), nullable=False)  # registry connection name
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class Transaction(Base):
    """A ledger entry: the single source of truth (INV-2).

    Append-only, enforced by database triggers created in migration 0001: rows
    are never deleted, and the only permitted update is setting ``voided_at``
    once. Corrections are ``voided_at`` on the old row plus a replacement row
    whose ``replaces_id`` points back. Positions are derived from these rows and
    never stored. Money carries an explicit currency (INV-9).
    """

    __tablename__ = "transactions"
    __table_args__ = (
        _currency_check("transactions"),
        _enum_check(
            "type",
            (
                "buy",
                "sell",
                "dividend",
                "deposit",
                "withdrawal",
                "fee",
                "split",
                "transfer_in",
                "transfer_out",
            ),
            "ck_transactions_type",
        ),
        _enum_check("source", ("manual", "import", "proposal"), "ck_transactions_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    security_id: Mapped[int | None] = mapped_column(
        ForeignKey("securities.id", ondelete="RESTRICT")
    )  # NULL for cash-only events
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(DecimalText)
    price: Mapped[Decimal | None] = mapped_column(DecimalText)
    amount: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # New shares per old share; only for type 'split'. Position semantics: T3 / P-4.
    split_ratio: Mapped[Decimal | None] = mapped_column(DecimalText)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT")
    )
    proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("proposals.id", ondelete="RESTRICT")
    )
    # P-3 dedup key, set by importers; NULL for manual rows.
    natural_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    replaces_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    account: Mapped["Account"] = relationship()
    security: Mapped["Security | None"] = relationship()


class Price(Base):
    """A daily closing price for a security, in the security's quote currency."""

    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("security_id", "price_date", "provider", name="uq_prices_security_date_provider"),
        _currency_check("prices"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)


class FxRate(Base):
    """A foreign-exchange rate for a pair named BASE_QUOTE.

    ``rate`` is units of QUOTE per 1 BASE, so USD_CAD 1.39 means 1 USD = 1.39 CAD
    (Bank of Canada FXUSDCAD). Keyed by pair so adding ZAR needs no schema
    change (D-11).
    """

    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("pair", "rate_date", "provider", name="uq_fx_rates_pair_date_provider"),
        CheckConstraint(
            "pair GLOB '[A-Z][A-Z][A-Z]_[A-Z][A-Z][A-Z]'", name="ck_fx_rates_pair_format"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pair: Mapped[str] = mapped_column(String(7), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)


class EtfConstituent(Base):
    """One holding of an ETF as of a date; ``weight`` is a fraction (0 to 1) of the fund."""

    __tablename__ = "etf_constituents"
    __table_args__ = (
        UniqueConstraint(
            "etf_security_id",
            "underlying_security_id",
            "as_of_date",
            name="uq_etf_constituents_etf_underlying_date",
        ),
        CheckConstraint(
            "etf_security_id != underlying_security_id", name="ck_etf_constituents_not_self"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    etf_security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False
    )
    underlying_security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="RESTRICT"), nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(DecimalText, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)


class Connection(Base):
    """A registry row for an outbound or inbound integration (INV-7).

    Disabled by default: nothing goes out until Musa switches it on. Holds only
    the NAME of the secret's env key, never the secret (INV-3).
    """

    __tablename__ = "connections"
    __table_args__ = (
        _enum_check(
            "kind", ("market_data", "news", "llm", "mcp_client"), "ck_connections_kind"
        ),
        _enum_check("direction", ("outbound", "inbound"), "ck_connections_direction"),
        CheckConstraint(
            "(kind = 'mcp_client' AND direction = 'inbound') "
            "OR (kind != 'mcp_client' AND direction = 'outbound')",
            name="ck_connections_kind_direction",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: fields that may be sent/read
    # The NAME of the .env key, never its value (INV-3).
    secret_env_key: Mapped[str | None] = mapped_column(String(64))
    # Nothing goes out until Musa switches it on (INV-7).
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)


class OutboundLog(Base):
    """One logged outbound call (INV-7). Records tickers only (INV-4)."""

    __tablename__ = "outbound_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="RESTRICT"), nullable=False
    )
    called_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(256), nullable=False)
    # JSON list of tickers: never quantities, values or account data (INV-4).
    tickers_sent: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    succeeded: Mapped[bool | None] = mapped_column(Boolean)


class AuthSession(Base):
    """A server-side login session for the single user (P-5, INV-3).

    Only the sha256 hex of the session token is stored, never the raw token, so
    a leaked database cannot be replayed as a cookie. Sessions are revocable
    (``revoked_at``) and slide forward while in use. All datetimes are naive UTC.
    Not part of the ledger: no money, no account data.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(256))
