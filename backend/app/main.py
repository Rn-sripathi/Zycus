"""FastAPI application.

Serves the API and, in production, the built React bundle from the same origin --
one deployable unit, no CORS configuration.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import STATIC_DIR
from app.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the Postgres pool on startup, close it on shutdown.

    A database that is unreachable must not stop the service booting: reviewing a
    contract does not depend on persistence, so a failure here is logged and the
    app carries on without an audit trail.
    """
    try:
        await db.connect()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception(
            "Could not reach the database; continuing without persistence"
        )

    yield

    await db.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zycus Redlining Agent",
        description=(
            "Reviews a counterparty contract against the Zycus playbook, proposes "
            "redline language, and separates findings it can verify from findings a "
            "human needs to judge."
        ),
        version="1.1.0",
        lifespan=lifespan,
    )

    # Only needed for local development, where Vite serves the UI on another port.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA if it is present; skip silently in development."""
    if not STATIC_DIR.is_dir():
        return

    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR / "assets"),
        name="assets",
    )

    index = STATIC_DIR / "index.html"

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(index)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
