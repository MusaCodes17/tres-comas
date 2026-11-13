"""FastAPI application assembly only.

Job: build the FastAPI app and register routers. No domain logic here; routers
live in ``app/routers/`` and domain rules in ``app/services/``.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Tres Comas")

    @app.get("/health")
    def health() -> dict[str, str]:
        # Public liveness probe for Docker/Caddy; every other route will
        # require auth from T4.
        return {"status": "ok"}

    return app


app = create_app()
