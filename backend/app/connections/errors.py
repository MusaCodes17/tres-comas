"""Exceptions raised by the connection registry and the outbound client.

Job: give callers (the T7 poller, routers) distinct types to map to "not
configured", 400 and 502 without string matching.
"""


class ConnectionNotFound(LookupError):
    """No registry row has the requested name."""


class ConnectionDisabled(RuntimeError):
    """The registry row exists but is switched off (INV-7). No call was made."""


class ConnectionNotConfigured(RuntimeError):
    """The row needs a secret whose env var is missing or empty. No call was made."""


class ConnectionNotCallable(RuntimeError):
    """The row's kind cannot be called in v1 (news, llm, or any inbound kind)."""


class ScopeViolation(ValueError):
    """The URL or params fall outside the row's scope (INV-4). Raised before sending."""


class ProviderError(RuntimeError):
    """The provider failed (transport error or HTTP status >= 400). The call is logged."""
