from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.bot import texts
from sahifa.config import Settings
from sahifa.domain.lifecycle import DomainError
from sahifa.models import User
from sahifa.services import transfers
from sahifa.services.users import upsert_user

router = Router(name="start")


def webapp_button(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def main_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [webapp_button(texts.BTN_CREATE, settings.webapp_url)],
            [webapp_button(texts.BTN_MY, f"{settings.webapp_url}#/my")],
        ]
    )


async def _touch_user(session: AsyncSession, tg_user) -> tuple[User, bool]:
    is_new = await session.get(User, tg_user.id) is None
    return await upsert_user(session, tg_user.model_dump()), is_new


async def _offer_transfer(message: Message, session: AsyncSession, token: str, clock) -> None:
    try:
        transfer, museum = await transfers.get_pending(session, token, clock())
    except DomainError as e:
        await message.answer(texts.ERRORS.get(e.code, texts.ERRORS["transfer_invalid"]))
        return
    giver = await session.get(User, transfer.from_user_id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=texts.BTN_ACCEPT, callback_data=f"tr:ok:{token}"),
            InlineKeyboardButton(text=texts.BTN_DECLINE, callback_data=f"tr:no:{token}"),
        ]]
    )
    await message.answer(
        texts.TRANSFER_OFFER.format(giver=giver.first_name if giver else "?", title=museum.title),
        reply_markup=markup,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, settings: Settings, clock) -> None:
    user, is_new = await _touch_user(session, message.from_user)
    arg = (command.args or "").strip()

    if arg.startswith("ref_") and is_new and arg[4:].isdigit() and int(arg[4:]) != user.id:
        user.referrer_id = int(arg[4:])
    await session.commit()

    if arg.startswith("tr_"):
        await _offer_transfer(message, session, arg[3:], clock)
    elif arg.startswith("m_") and arg[2:].replace("-", "").replace("_", "").isalnum():
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[webapp_button(texts.BTN_OPEN_MUSEUM, f"{settings.webapp_url}#/m/{arg[2:]}")]]
        )
        await message.answer(texts.OPEN_MUSEUM, reply_markup=markup)
    else:
        await message.answer(
            texts.WELCOME.format(name=message.from_user.first_name), reply_markup=main_keyboard(settings)
        )


@router.callback_query(F.data.startswith("tr:"))
async def on_transfer_answer(callback: CallbackQuery, session: AsyncSession, settings: Settings, clock) -> None:
    _, answer, token = callback.data.split(":", 2)
    if answer != "ok":
        await callback.message.edit_text(texts.TRANSFER_DECLINED)
        await callback.answer()
        return
    user, _ = await _touch_user(session, callback.from_user)
    try:
        transfer, _museum = await transfers.get_pending(session, token, clock())
        museum = await transfers.accept_transfer(session, token, user, clock())
    except DomainError as e:
        await session.rollback()
        await callback.answer(texts.ERRORS.get(e.code, texts.ERRORS["transfer_invalid"]), show_alert=True)
        return
    await session.commit()
    await callback.message.edit_text(
        texts.TRANSFER_ACCEPTED.format(title=museum.title),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[webapp_button(texts.BTN_MY, f"{settings.webapp_url}#/my")]]),
    )
    await callback.answer()
    bot = getattr(callback, "bot", None)
    if bot is not None:
        await bot.send_message(
            transfer.from_user_id, texts.TRANSFER_DONE_GIVER.format(title=museum.title, taker=user.first_name)
        )
