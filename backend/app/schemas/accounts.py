"""Account request and response schemas (INV-8: no account-number field anywhere)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AccountType = Literal["tfsa", "rrsp", "non_registered", "cash"]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str
    type: AccountType
    base_currency: str = "CAD"
    broker_label: str | None = None


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = None
    type: AccountType | None = None
    broker_label: str | None = None


class AccountOut(BaseModel):
    id: int
    nickname: str
    type: str
    base_currency: str
    broker_label: str | None
    last_reconciled_date: date | None
    created_at: datetime
