"""The FastAPI application.

Thin by design: routers come from the use-case files, and the only thing
assembled here is the edge -- CORS, error translation, health.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from seebach.platform.config import settings
from seebach.platform.errors import DomainError
from seebach.platform.migrate import upgrade_to_head
from seebach.registry import api_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = settings()
    if config.migrate_on_start:
        upgrade_to_head(config.database_url)
    yield


def create_app() -> FastAPI:
    config = settings()
    app = FastAPI(
        title="Seebach",
        version="0.1.0",
        summary="Digital result entry for chess tournaments run in Swiss-Manager or Vega",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.as_dict())

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router(), prefix="/api")
    return app


app = create_app()
