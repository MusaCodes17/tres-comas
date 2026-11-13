"""Exact decimal column type for SQLite.

Job: map ``decimal.Decimal`` values to and from TEXT columns, so every money
and quantity column round-trips exactly. Nothing else.

Rationale: SQLite has no decimal type. SQLAlchemy ``Numeric`` on SQLite goes
through float affinity and silently loses precision (AGENTS.md §6). Storing the
canonical plain-notation string keeps every digit; all arithmetic happens in
Python on ``Decimal`` objects.

Invariants: INV-9 (money and quantities are decimals, never floats). A float or
bool is refused at bind time instead of being coerced. Decision D-15 (formerly
P-1 in ``docs/design_decisions.md``).
"""

import decimal
from decimal import Decimal
from typing import Any

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class DecimalText(TypeDecorator):
    """Decimal stored as exact TEXT in plain positional notation.

    Values are compared and summed in Python only. SQL ``ORDER BY``, ``SUM``,
    ``MIN``/``MAX`` or numeric comparison on these columns is meaningless,
    because the database sees text.

    Scale is preserved: ``Decimal("1.2500")`` is stored as ``"1.2500"``. Nothing
    is normalised.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        """Convert a Python value to its canonical decimal string.

        Raises:
            TypeError: For bool, float, or any type other than None, int, str or Decimal.
            ValueError: For a string that is not a number, or for NaN or infinity.
        """
        if value is None:
            return None
        if isinstance(value, bool):
            raise TypeError(
                "DecimalText refuses bool; construct Decimal from a string (INV-9)"
            )
        if isinstance(value, float):
            raise TypeError(
                "DecimalText refuses float; construct Decimal from a string (INV-9)"
            )
        if isinstance(value, int):
            dec = Decimal(value)
        elif isinstance(value, str):
            try:
                dec = Decimal(value)
            except decimal.InvalidOperation as exc:
                raise ValueError(f"DecimalText cannot parse {value!r}") from exc
        elif isinstance(value, Decimal):
            dec = value
        else:
            raise TypeError(
                f"DecimalText refuses {type(value).__name__}; construct Decimal from a string (INV-9)"
            )
        if dec.is_nan() or dec.is_infinite():
            raise ValueError(f"DecimalText refuses non-finite value {value!r}")
        return format(dec, "f")

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        """Parse a stored decimal string back into a Decimal."""
        if value is None:
            return None
        return Decimal(value)
