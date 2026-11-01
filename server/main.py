"""WeWin API server.

Production (Docker):  the entrypoint runs `python -m server.manage init`, then uvicorn server.main:app
Development:          python -m server.main     (same initialisation, then serves)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from server import __version__
from server.app.api.router import api_router
from server.app.core.config import settings
from server.app.services.errors import ServiceError


def create_app() -> FastAPI:
    production = settings.environment == "production"
    app = FastAPI(
        title="WeWin API",
        version=__version__,
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )

    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # One human-readable message, the same shape as HTTPException responses.
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        message = str(first.get("msg", "Invalid request.")).removeprefix("Value error, ")
        if field and field != "email":
            message = f"{field}: {message}"
        return JSONResponse(status_code=422, content={"detail": message})

    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    from server.manage import init

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init()
    uvicorn.run(app, host=settings.host, port=settings.port)
