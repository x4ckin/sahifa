from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker

from sahifa.api.auth import AuthError
from sahifa.config import Settings
from sahifa.domain.lifecycle import DomainError
from sahifa.models import Order

STATUS_BY_CODE = {
    "not_found": 404,
    "locked": 409,
    "slots_full": 409,
    "media_full": 409,
    "not_editable": 409,
    "too_large": 413,
}

InvoiceLinkFactory = Callable[[Order], Awaitable[str]]
ReceiptNotifier = Callable[[Order], Awaitable[None]]


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def create_app(
    settings: Settings,
    sessionmaker: async_sessionmaker,
    *,
    invoice_link_factory: InvoiceLinkFactory,
    receipt_notifier: ReceiptNotifier,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    from sahifa.api import routes_me, routes_museums

    app = FastAPI(title="Sahifa API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.sessionmaker = sessionmaker
    app.state.clock = clock
    app.state.invoice_link_factory = invoice_link_factory
    app.state.receipt_notifier = receipt_notifier

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_origin(settings.webapp_url)],
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Telegram-Init-Data"],
    )

    @app.exception_handler(AuthError)
    async def _auth_error(_: Request, exc: AuthError):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError):
        return JSONResponse({"error": exc.code}, status_code=STATUS_BY_CODE.get(exc.code, 400))

    for router in (routes_me.router, routes_museums.router):
        app.include_router(router, prefix="/api")

    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    return app
