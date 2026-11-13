"""Provider modules: one file per outbound provider (prices, FX, ETF holdings).

Each provider goes through ``connections.call``; none opens its own HTTP client.
Provider modules arrive in T7.
"""
