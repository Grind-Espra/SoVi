from __future__ import annotations
import html
import time
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from .. import db

router = Router()

async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        return (await bot.get_chat_member(chat_id, user_id)).status in {"creator", "administrator"}
    except Exception:
        return False

async def premium_info(bot, settings, chat_id: int) -> str:
    try:
        title = (await bot.get_chat(chat_id)).title or str(chat_id)
    except Exception:
        title = str(chat_id)
    until = await db.get_premium_until(settings.db_path, chat_id)
    active = bool(until and until > time.time())
    state = f"✅ Активен до <b>{time.strftime('%d.%m.%Y', time.localtime(until))}</b>" if active else "▫️ Сейчас не подключён"
    return (
        "💎 <b>SoVi Premium</b>\n\n"
        f"<b>{html.escape(title)}</b>\n\n{state}\n\n"
        "<b>Что даёт:</b>\n"
        "• 👥 до <b>25 игроков</b> вместо 12\n"
        "• 📝 до <b>100 вопросов</b> за игру\n"
        "• 🎛 расширенные варианты настроек\n\n"
        f"💳 Стоимость: <b>{settings.premium_stars} ⭐ / 30 дней</b>.\n\n"
        "Premium привязан к этой группе и не даёт игровых преимуществ."
    )

@router.message(Command("premium"))
async def premium_group(message: Message, settings):
    if message.chat.type == ChatType.PRIVATE:
        return await message.answer("💎 Premium покупается для конкретной группы. В нужной группе нажмите /premium.")
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        return await message.answer("⛔ Premium может подключить только администратор группы.")
    try:
        await message.delete()
    except Exception:
        pass
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=premium_{message.chat.id}"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "💎 <b>SoVi Premium</b>\n\nПокупка проходит в личном чате с ботом.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Открыть Premium", url=link)]])
    )

@router.callback_query(F.data.startswith("premium:buy:"))
async def buy(callback: CallbackQuery, settings):
    chat_id = int(callback.data.rsplit(":", 1)[1])
    if not await is_admin(callback.bot, chat_id, callback.from_user.id):
        return await callback.answer("⛔ Только администратор этой группы.", show_alert=True)
    until = await db.get_premium_until(settings.db_path, chat_id)
    if until and until > time.time():
        return await callback.answer("Premium уже активен.", show_alert=True)
    await callback.answer()
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="SoVi Premium",
        description="Premium для одной группы: до 25 игроков и до 100 вопросов. Срок 30 дней.",
        payload=f"premium:{chat_id}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="SoVi Premium • 30 дней", amount=settings.premium_stars)],
        provider_token="",
        subscription_period=2592000,
    )

@router.callback_query(F.data.startswith("premium:status:"))
async def status(callback: CallbackQuery, settings):
    chat_id = int(callback.data.rsplit(":", 1)[1])
    if not await is_admin(callback.bot, chat_id, callback.from_user.id):
        return await callback.answer("⛔ Только администратор этой группы.", show_alert=True)
    await callback.answer()
    await callback.message.edit_text(await premium_info(callback.bot, settings, chat_id))

@router.pre_checkout_query()
async def precheckout(query: PreCheckoutQuery):
    if not query.invoice_payload.startswith("premium:"):
        return await query.answer(ok=False, error_message="Неизвестный платёж.")
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def paid(message: Message, settings):
    p = message.successful_payment
    parts = p.invoice_payload.split(":")
    if len(parts) != 3 or parts[0] != "premium":
        return
    chat_id, admin_id = int(parts[1]), int(parts[2])
    if admin_id != message.from_user.id:
        return
    until = getattr(p, "subscription_expiration_date", None) or int(time.time() + 2592000)
    await db.set_chat_premium(settings.db_path, chat_id, until, message.from_user.id, getattr(p, "telegram_payment_charge_id", None))
    await message.answer(
        f"💎 <b>Premium подключён!</b>\n\n"
        f"До <b>{time.strftime('%d.%m.%Y', time.localtime(until))}</b>.\n"
        "👥 Лимит: <b>25 игроков</b>.\n📝 Игра: до <b>100 вопросов</b>."
    )
    try:
        await message.bot.send_message(chat_id, "💎 <b>SoVi Premium активирован.</b> Теперь лимит — <b>25 игроков</b>, а размер игры — до <b>100 вопросов</b>.")
    except Exception:
        pass
