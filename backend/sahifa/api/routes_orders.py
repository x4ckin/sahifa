import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.api.auth import current_user, get_session
from sahifa.api.routes_museums import _spooled
from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import Product
from sahifa.models import Museum, Order, User
from sahifa.services import orders as svc
from sahifa.services.media import MAX_IMAGE_BYTES
from sahifa.services.settings_store import get_cards

log = logging.getLogger(__name__)
router = APIRouter()


class OrderIn(BaseModel):
    product: str
    museum_id: int | None = None
    method: Literal["stars", "card"]


def order_out(order: Order) -> dict:
    return {
        "code": order.code,
        "status": order.status,
        "product": order.product,
        "method": order.method,
        "museum_id": order.museum_id,
        "amount_uzs": order.amount_uzs,
        "amount_stars": order.amount_stars,
        "reject_reason": order.reject_reason,
    }


async def _own_order(s: AsyncSession, user: User, code: str) -> Order:
    order = await svc.get_by_code(s, code)
    if order.user_id != user.id:
        raise DomainError("not_found")
    return order


@router.post("/orders")
async def create(body: OrderIn, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    try:
        product = Product(body.product)
    except ValueError as e:
        raise DomainError("bad_order") from e
    order = await svc.create_order(s, user, product, body.museum_id, body.method, request.app.state.clock())
    out = order_out(order)
    if order.status == "pending" and order.method == "stars":
        rooms = (await s.get(Museum, order.museum_id)).extra_rooms if order.product == Product.MUSEUM else 0
        out["invoice_link"] = await request.app.state.invoice_link_factory(order, rooms)
    elif order.method == "card" and order.status in ("pending", "rejected", "awaiting_review"):
        out["cards"] = await get_cards(s)
        out["comment"] = order.code
    await s.commit()
    return out


@router.get("/orders/{code}")
async def get(code: str, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    order = await _own_order(s, user, code)
    out = order_out(order)
    if order.method == "card" and order.status in ("pending", "rejected", "cancelled"):
        out["cards"] = await get_cards(s)  # the screen may be reopened later: it needs the details again
        out["comment"] = order.code
    return out


@router.post("/orders/{code}/receipt")
async def receipt(
    code: str, request: Request, file: UploadFile = File(...),
    user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
):
    order = await _own_order(s, user, code)
    if not (file.content_type or "").startswith("image/"):
        raise DomainError("bad_format")
    with _spooled(file, MAX_IMAGE_BYTES) as src:
        await svc.attach_receipt(
            s, order, src, request.app.state.clock(), receipts_dir=request.app.state.settings.receipts_dir
        )
    await s.commit()
    try:
        await request.app.state.receipt_notifier(order)
    except Exception:  # the receipt is saved; admins can list it with /cheklar
        log.exception("could not notify admins about receipt %s", order.code)
    return order_out(order)
