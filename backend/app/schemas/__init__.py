"""Pydantic schemas at the API boundary only (no domain rules).

Job: request and response shapes. Decimals leave the API as strings (INV-9)
via ``dec_str``; request decimal fields are typed ``str`` so a JSON number is
refused with 422 and the exact string reaches the ledger unchanged.
"""

from decimal import Decimal


def dec_str(value: Decimal | None) -> str | None:
    """Render a Decimal as a plain string, never scientific notation (INV-9)."""
    if value is None:
        return None
    return format(value, "f")
