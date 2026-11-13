"""Connection registry request and response schemas (INV-3: no secret value field anywhere).

Job: request and response shapes for ``/api/connections``. A create names an env
key by NAME only; responses report whether it is set, never its value. Rows are
created disabled and can only be switched on or off here (INV-7); there is no delete.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool

ConnectionKind = Literal["market_data", "news", "llm", "mcp_client"]


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: ConnectionKind
    scope: dict[str, Any]
    secret_env_key: str | None = None


class ConnectionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class ConnectionOut(BaseModel):
    """Mirrors ``registry.public_view``: the env key name and ``secret_configured``, never a value."""

    id: int
    name: str
    kind: str
    direction: str
    scope: dict[str, Any]
    secret_env_key: str | None
    secret_configured: bool
    enabled: bool
    created_at: datetime
    last_used_at: datetime | None


class ConnectionLogOut(BaseModel):
    """One outbound log row. ``tickers_sent`` only (INV-4)."""

    id: int
    called_at: datetime
    endpoint: str
    tickers_sent: list[str]
    succeeded: bool | None
