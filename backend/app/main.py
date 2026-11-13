"""FastAPI application assembly only.

Job: build the FastAPI app and register routers. No domain logic here; routers
live in ``app/routers/`` and domain rules in ``app/services/``.

Default deny (INV-3): ``require_session`` is an app-level dependency, so every
route needs a valid session except those in ``deps.PUBLIC_PATHS``. Interactive
docs and the OpenAPI schema are off: they would list every route unauthenticated.
"""

from fastapi import Depends, FastAPI

from app.routers import accounts as accounts_router
from app.routers import auth as auth_router
from app.routers import connections as connections_router
from app.routers import securities as securities_router
from app.routers import transactions as transactions_router
from app.routers.deps import require_session


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Tres Comas",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(require_session)],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        # Public liveness probe for Docker/Caddy (in deps.PUBLIC_PATHS); every
        # other route requires a session.
        return {"status": "ok"}

    app.include_router(auth_router.router)
    app.include_router(accounts_router.router)
    app.include_router(securities_router.router)
    app.include_router(transactions_router.router)
    app.include_router(connections_router.router)

    return app


app = create_app()
