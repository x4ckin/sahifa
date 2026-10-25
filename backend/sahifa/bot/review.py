"""Card-transfer receipts: send to the admin chat, approve or reject with one tap."""

from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sahifa.bot import texts
from sahifa.bot.start import webapp_button
from sahifa.config import Settings
from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import PRODUCT_TITLES_UZ, Product
from sahifa.models import Museum, Order, User
from sahifa.services import orders

escape = html_decoration.quote  # &, <, > only — apostrophes in names stay readable

router = Router(name="review")


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def review_keyboard(code: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=texts.BTN_APPROVE, callback_data=f"rv:ok:{code}")]]
    rows += [
        [InlineKeyboardButton(text=f"❌ {label}", callback_data=f"rv:no:{code}:{key}")]
        for key, label in texts.REJECT_REASONS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def notify_admins_new_receipt(bot, settings: Settings, session: AsyncSession, order: Order) -> None:
    user = await session.get(User, order.user_id)
    museum = await session.get(Museum, order.museum_id) if order.museum_id else None
    caption = texts.RECEIPT_CAPTION.format(
        code=order.code,
        user=escape(user.first_name if user else "?") + (f" @{escape(user.username)}" if user and user.username else ""),
        user_id=order.user_id,
        product=PRODUCT_TITLES_UZ[Product(order.product)],
        museum=escape(museum.title) if museum else "—",
        amount=money(order.amount_uzs),
    )
    await bot.send_photo(
        settings.admin_chat_id,
        FSInputFile(settings.receipts_dir / order.receipt_path),
        caption=caption,
        reply_markup=review_keyboard(order.code),
    )


def make_receipt_notifier(bot, settings: Settings, sessionmaker: async_sessionmaker) -> Callable[[Order], Awaitable[None]]:
    """The API calls this after a receipt upload (it runs in its own session)."""

    async def notify(order: Order) -> None:
        async with sessionmaker() as session:
            fresh = await orders.get_by_code(session, order.code)
            await notify_admins_new_receipt(bot, settings, session, fresh)

    return notify


async def _safe(coro) -> None:
    """Telegram side effects after a commit must never undo or hide the decision."""
    try:
        await coro
    except TelegramAPIError:
        pass


@router.callback_query(F.data.startswith("rv:"))
async def on_review(callback: CallbackQuery, session: AsyncSession, bot, settings: Settings, clock) -> None:
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer(texts.NOT_ADMIN, show_alert=True)
        return
    parts = callback.data.split(":")
    try:
        action, code = parts[1], parts[2]
        order = await orders.get_by_code(session, code)
    except (IndexError, DomainError):
        await callback.answer(texts.REVIEW_ALREADY, show_alert=True)
        return
    if not await orders.claim_for_review(session, order):  # double tap, or another admin was first
        await callback.answer(texts.REVIEW_ALREADY, show_alert=True)
        return

    admin = escape(callback.from_user.first_name)
    message = callback.message
    caption = getattr(message, "html_text", None) or ""
    product = PRODUCT_TITLES_UZ[Product(order.product)]
    if action == "ok":
        try:
            await orders.fulfil(session, order, clock(), admin_id=callback.from_user.id)
        except DomainError as e:  # museum deleted or already paid: order is rejected, money must go back
            await session.commit()
            await callback.answer()
            gone = e.code == "museum_gone"
            note = texts.REVIEW_MUSEUM_GONE if gone else texts.REVIEW_ALREADY_PAID
            await _safe(message.edit_caption(caption=caption + note, reply_markup=None))
            await _safe(bot.send_message(order.user_id, texts.USER_MUSEUM_GONE if gone else texts.USER_ALREADY_PAID))
            return
        await session.commit()
        await callback.answer()
        await _safe(message.edit_caption(caption=caption + texts.REVIEW_APPROVED.format(admin=admin), reply_markup=None))
        my_button = InlineKeyboardMarkup(inline_keyboard=[[webapp_button(texts.BTN_MY, f"{settings.webapp_url}#/my")]])
        await _safe(bot.send_message(order.user_id, texts.USER_APPROVED.format(product=product), reply_markup=my_button))
        return

    reason_key = parts[3] if len(parts) > 3 and parts[3] in texts.REJECT_REASONS else "notfound"
    reason = texts.REJECT_REASONS[reason_key]
    await orders.reject(session, order, callback.from_user.id, reason_key, clock())
    await session.commit()
    await callback.answer()
    await _safe(message.edit_caption(caption=caption + texts.REVIEW_REJECTED.format(reason=reason, admin=admin), reply_markup=None))
    resend = InlineKeyboardMarkup(
        inline_keyboard=[[webapp_button(texts.BTN_RESEND, f"{settings.webapp_url}#/order/{order.code}")]]
    )
    await _safe(bot.send_message(order.user_id, texts.USER_REJECTED.format(reason=reason.lower()), reply_markup=resend))
