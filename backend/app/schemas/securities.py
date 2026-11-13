"""Security request and response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

SecurityKind = Literal["stock", "etf", "cash"]


class SecurityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    exchange: str
    currency: str
    kind: SecurityKind
    name: str | None = None
    sector: str | None = None


class SecurityOut(BaseModel):
    id: int
    ticker: str
    exchange: str
    currency: str
    kind: str
    name: str | None
    sector: str | None
