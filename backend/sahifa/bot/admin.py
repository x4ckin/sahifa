"""Admin commands. Only users listed in SAHIFA_ADMIN_IDS reach these handlers."""

import asyncio
import re
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.bot.review import money
from sahifa.config import Settings
from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import Product
from sahifa.models import Museum, Order, User
from sahifa.services import orders
from sahifa.services.settings_store import get_price, set_cards, set_price
from sahifa.services.users import find_user, grant_free, list_free, revoke_free

escape = html_decoration.quote  # &, <, > only — apostrophes in names stay readable

TASHKENT = timezone(timedelta(hours=5))
router = Router(name="admin")


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message, settings: Settings) -> bool:
        return message.from_user is not None and message.from_user.id in settings.admin_ids


router.message.filter(IsAdmin())

PRICE_USAGE = "Foydalanish: /narx <museum|reactivate|room|slots> <uzs|stars> <son>"


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, clock) -> None:
    now = clock()
    day_start = now.astimezone(TASHKENT).replace(hour=0, minute=0, second=0, microsecond=0)
    users = await session.scalar(select(func.count()).select_from(User))
    by_status = dict((await session.execute(select(Museum.status, func.count()).group_by(Museum.status))).all())

    async def paid(since: datetime | None) -> tuple[int, int, int]:
        """(paid orders, card so'm, Stars) — free grants are not revenue."""
        where = [Order.status == "paid", Order.method != "free"]
        if since is not None:
            where.append(Order.paid_at >= since)
        count = await session.scalar(select(func.count()).select_from(Order).where(*where))
        card = await session.scalar(select(func.coalesce(func.sum(Order.amount_uzs), 0)).where(*where, Order.method == "card"))
        stars = await session.scalar(select(func.coalesce(func.sum(Order.amount_stars), 0)).where(*where, Order.method == "stars"))
        return count, card, stars

    today, total = await paid(day_start), await paid(None)
    museums = ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())) or "—"
    await message.answer(
        f"📊 <b>Statistika</b>\n"
        f"Foydalanuvchilar: {users}\n"
        f"Muzeylar — {museums}\n"
        f"Bugun: {today[0]} ta to'lov, {money(today[1])} so'm + {today[2]} ⭐\n"
        f"Jami: {total[0]} ta to'lov, {money(total[1])} so'm + {total[2]} ⭐"
    )


@router.message(Command("narx"))
async def cmd_price(message: Message, command: CommandObject, session: AsyncSession) -> None:
    if not command.args:
        lines = [
            f"{p.value}: {money(await get_price(session, p, 'uzs'))} so'm / {await get_price(session, p, 'stars')} ⭐"
            for p in Product
        ]
        await message.answer("💰 Narxlar:\n" + "\n".join(lines) + "\n\n" + PRICE_USAGE)
        return
    parts = command.args.split()
    try:
        product, currency, value = Product(parts[0]), parts[1], int(parts[2])
        if currency not in ("uzs", "stars") or value < 1:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(PRICE_USAGE)
        return
    await set_price(session, product, currency, value)
    await session.commit()
    await message.answer(f"✅ {product.value} narxi: {money(value)} {currency}")


CARD_LINE = re.compile(r"^\s*([\d ]{12,23}?)\s+(\D.+?)\s*$")


@router.message(Command("karta"))
async def cmd_cards(message: Message, command: CommandObject, session: AsyncSession) -> None:
    args = (command.args or "").strip()
    if args == "tozalash":
        await set_cards(session, [])
        await session.commit()
        await message.answer("✅ Kartalar o'chirildi.")
        return
    cards = []
    for line in args.splitlines():
        m = CARD_LINE.match(line)
        if m is None:
            await message.answer("Foydalanish: /karta 8600 1234 5678 9012 Ism Familiya (har karta yangi qatorda)")
            return
        cards.append({"number": " ".join(m.group(1).split()), "holder": m.group(2)})
    if not cards:
        await message.answer("Foydalanish: /karta 8600 1234 5678 9012 Ism Familiya | /karta tozalash")
        return
    await set_cards(session, cards)
    await session.commit()
    await message.answer("✅ Kartalar saqlandi:\n" + "\n".join(f"{c['number']} — {escape(c['holder'])}" for c in cards))


async def _target(message: Message, session: AsyncSession, ref: str | None) -> User | None:
    if ref:
        return await find_user(session, ref)
    replied = message.reply_to_message
    if replied is None:
        return None
    source = getattr(replied, "forward_from", None) or replied.from_user
    return await session.get(User, source.id) if source else None


@router.message(Command("bepul"))
async def cmd_free(message: Message, command: CommandObject, session: AsyncSession, bot, clock) -> None:
    parts = (command.args or "").split()
    days = None
    if parts and parts[-1].isdigit() and (len(parts) == 2 or message.reply_to_message is not None):
        days = int(parts.pop())
    ref = parts[0] if parts else None
    user = await _target(message, session, ref)
    if user is None:
        await message.answer("Foydalanuvchi topilmadi. U avval botga /start bosgan bo'lishi kerak.\n"
                             "Foydalanish: /bepul <id|@username> [kun] yoki xabariga reply qilib /bepul [kun]")
        return
    await grant_free(session, user.id, message.from_user.id, days, clock())
    await session.commit()
    until = f"{days} kun" if days else "muddatsiz"
    await message.answer(f"✅ {escape(user.first_name)} (<code>{user.id}</code>) — bepul ({until}).")
    try:
        await bot.send_message(user.id, f"🎁 Sizga Sahifa'dan bepul foydalanish huquqi berildi ({until}).")
    except (TelegramForbiddenError, TelegramBadRequest):
        pass


@router.message(Command("bepul_ochir"))
async def cmd_unfree(message: Message, command: CommandObject, session: AsyncSession) -> None:
    user = await _target(message, session, (command.args or "").strip() or None)
    if user is None:
        await message.answer("Foydalanuvchi topilmadi. Foydalanish: /bepul_ochir <id|@username>")
        return
    await revoke_free(session, user.id, message.from_user.id)
    await session.commit()
    await message.answer(f"✅ {escape(user.first_name)} — bepul maqomi olib tashlandi.")


@router.message(Command("bepullar"))
async def cmd_free_list(message: Message, session: AsyncSession) -> None:
    users = await list_free(session)
    if not users:
        await message.answer("Bepul foydalanuvchilar yo'q.")
        return
    lines = [
        f"• {escape(u.first_name)} {('@' + escape(u.username)) if u.username else ''} <code>{u.id}</code> — "
        + (u.free_until.astimezone(TASHKENT).strftime("%d.%m.%Y gacha") if u.free_until else "muddatsiz")
        for u in users
    ]
    await message.answer("🎁 Bepul foydalanuvchilar:\n" + "\n".join(lines))


@router.message(Command("xabar"))
async def cmd_broadcast(message: Message, session: AsyncSession, bot, delay: float = 0.04) -> None:
    source = message.reply_to_message
    if source is None:
        await message.answer("Yubormoqchi bo'lgan xabarga reply qilib /xabar yozing.")
        return
    ids = (await session.scalars(select(User.id).where(User.blocked_bot.is_(False)))).all()
    await message.answer(f"📤 {len(ids)} ta foydalanuvchiga yuborilmoqda…")
    sent = blocked = failed = 0
    for uid in ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=source.chat.id, message_id=source.message_id)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            failed += 1
        except TelegramForbiddenError:
            user = await session.get(User, uid)
            user.blocked_bot = True
            blocked += 1
        except TelegramBadRequest:
            failed += 1
        await asyncio.sleep(delay)  # stay under ~25 messages per second
    await session.commit()
    await message.answer(f"✅ Yuborildi: {sent}\n🚫 Bloklagan: {blocked}\n⚠️ Xato: {failed}")


@router.message(Command("qaytar"))
async def cmd_refund(message: Message, command: CommandObject, session: AsyncSession, bot, clock) -> None:
    try:
        order = await orders.get_by_code(session, (command.args or "").strip())
        if order.method != "stars" or order.status != "paid" or not order.charge_id:
            raise DomainError("bad_order")
    except DomainError:
        await message.answer("Foydalanish: /qaytar <kod> — faqat to'langan Stars buyurtmalari uchun.")
        return
    await bot.refund_star_payment(user_id=order.user_id, telegram_payment_charge_id=order.charge_id)
    await orders.mark_refunded(session, order, message.from_user.id, clock())
    await session.commit()
    await message.answer(f"✅ {order.code}: {order.amount_stars} ⭐ qaytarildi.")
