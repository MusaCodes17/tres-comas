"""The connection registry and the only module that makes outbound HTTP (INV-7).

Public surface: ``call`` and the error types. Registry CRUD lives in
``connections.registry``.
"""
from app.connections.client import call
from app.connections.errors import (
    ConnectionDisabled,
    ConnectionNotCallable,
    ConnectionNotConfigured,
    ConnectionNotFound,
    ProviderError,
    ScopeViolation,
)

__all__ = [
    "call",
    "ConnectionDisabled",
    "ConnectionNotCallable",
    "ConnectionNotConfigured",
    "ConnectionNotFound",
    "ProviderError",
    "ScopeViolation",
]
