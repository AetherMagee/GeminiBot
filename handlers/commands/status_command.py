import datetime
import random

from aiogram.types import Message

import api.google
import api.openai
import db
from main import start_time
from utils import log_command


def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if days > 0:
        parts.append(f"{days} дн")
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} сек")
    return ', '.join(parts)


async def status_command(message: Message):
    if await db.is_blacklisted(message.from_user.id):
        await message.reply("❌ <b>Вы были внесены в чёрный список бота. Ваши сообщения не обрабатываются.</b>")
        return
    if await db.is_blacklisted(message.chat.id):
        await message.reply("❌ <b>Этот чат был внесён в чёрный список бота. Сообщения отсюда не обрабатываются.</b>")
        return

    await log_command(message)

    messages = await db.get_messages(message.chat.id)

    messages_limit = await db.get_chat_parameter(message.chat.id, "message_limit")
    endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    model = await db.get_chat_parameter(message.chat.id, endpoint[0] + "_model")
    rate_limit = await db.get_chat_parameter(message.chat.id, "max_requests_per_hour")

    request_count = await db.get_request_count(message.chat.id, datetime.timedelta(hours=1))
    uptime = datetime.datetime.now() - start_time

    token_count_text = "⏱ Секунду..." if endpoint == "google" else str(
        await api.openai.count_tokens(message.chat.id)) + " токенов"
    quota_text = "не ограничен" if rate_limit == 0 else f"{request_count}/{rate_limit}"
    if request_count >= rate_limit:
        quota_text = quota_text + " ⚠️"

    text_to_send = f"""👋 <b>Я тут!</b>

💬 <b>Память:</b> {len(messages)}/{messages_limit} сообщений <i>({token_count_text})</i>
✨ <b>Модель:</b> <i>{model}</i>
📊 <b>Лимит запросов в час:</b> <i>{quota_text}</i>

🆔 <b>ID чата:</b> <code>{message.chat.id}</code>
⏱ <b>Аптайм:</b> {format_timedelta(uptime)}
"""
    if random.randint(1, 6) == 3 or request_count >= rate_limit:
        text_to_send += "\nℹ️ <b>Нужна помощь с ботом?</b> - /feedback"

    reply = await message.reply(text_to_send)

    if endpoint == "google":
        token_count_text = await api.google.count_tokens_for_chat(message)
        text_to_send = text_to_send.replace("⏱ Секунду...", f"{token_count_text} токенов")
        await reply.edit_text(text_to_send)
