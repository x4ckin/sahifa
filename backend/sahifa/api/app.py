from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
    "start_bot": 409,
    "bad_token": 404,
    "media_gone": 410,
    "telegram_unavailable": 503,
    "already_paid": 409,
    "payment_in_review": 409,
}

InvoiceLinkFactory = Callable[[Order, int], Awaitable[str]]  # (order, extra rooms in it)
ReceiptNotifier = Callable[[Order], Awaitable[None]]
TgUploader = Callable[[int, Path, str], Awaitable[str]]  # (user_id, file, kind) -> Telegram file_id
TgFetcher = Callable[[str], Awaitable[bytes]]  # file_id -> content (<= 20 MB), never written to disk


async def _not_configured(*_args):
    raise RuntimeError("Telegram media bridge is not configured")


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def create_app(
    settings: Settings,
    sessionmaker: async_sessionmaker,
    *,
    invoice_link_factory: InvoiceLinkFactory,
    receipt_notifier: ReceiptNotifier,
    tg_uploader: TgUploader = _not_configured,
    tg_fetcher: TgFetcher = _not_configured,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    max_body_bytes: int = 60 * 2**20,
) -> FastAPI:
    from sahifa.api import (
        routes_me, routes_museums, routes_orders, routes_prices, routes_public, routes_tgmedia, routes_transfers,
    )

    app = FastAPI(title="Sahifa API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.sessionmaker = sessionmaker
    app.state.clock = clock
    app.state.invoice_link_factory = invoice_link_factory
    app.state.receipt_notifier = receipt_notifier
    app.state.tg_uploader = tg_uploader
    app.state.tg_fetcher = tg_fetcher

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_origin(settings.webapp_url)],
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Telegram-Init-Data"],
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse({"error": "bad_field"}, status_code=400)

    @app.exception_handler(AuthError)
    async def _auth_error(_: Request, exc: AuthError):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError):
        return JSONResponse({"error": exc.code}, status_code=STATUS_BY_CODE.get(exc.code, 400))

    for module in (routes_me, routes_museums, routes_orders, routes_transfers, routes_public, routes_tgmedia, routes_prices):
        app.include_router(module.router, prefix="/api")

    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    return BodyLimit(app, max_body_bytes)


class BodyLimit:
    """Refuse oversized bodies before anything parses them (multipart is spooled before auth runs).

    Bodies must declare Content-Length; browsers and Telegram's WebView always do for fetch/FormData.
    """

    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes
        self.state = app.state  # keep `app.state` reachable for callers and tests

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in ("POST", "PUT", "PATCH"):
            length = dict(scope["headers"]).get(b"content-length")
            if length is None or not length.isdigit():
                return await JSONResponse({"error": "length_required"}, status_code=411)(scope, receive, send)
            if int(length) > self.max_bytes:
                return await JSONResponse({"error": "too_large"}, status_code=413)(scope, receive, send)
            receive = self._capped(receive)
        await self.app(scope, receive, send)

    def _capped(self, receive):
        seen = 0

        async def wrapped():
            nonlocal seen
            message = await receive()
            seen += len(message.get("body", b""))
            if seen > self.max_bytes:  # body longer than its Content-Length claimed
                return {"type": "http.disconnect"}
            return message

        return wrapped
