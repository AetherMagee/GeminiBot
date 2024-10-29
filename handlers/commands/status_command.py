import datetime

from aiogram.types import Message

import api.google
import api.openai
import db
from utils import log_command


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

    current_endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    if current_endpoint == "openai":
        table_prefix = "o_"
    elif current_endpoint == "google":
        table_prefix = "g_"
    else:
        table_prefix = "o_"
    current_model = await db.get_chat_parameter(message.chat.id, table_prefix + "model")

    token_count = "⏱ Секунду..."

    if current_endpoint == "openai":
        token_count = str(await api.openai.count_tokens(message.chat.id)) + " токенов"

    text_to_send = f"""👋 <b>Я тут!</b>

💬 <b>Память:</b> {len(messages)}/{messages_limit} сообщений <i>({token_count})</i>
✨ <b>Модель:</b> <i>{current_model}</i>
🆔 <b>ID чата:</b> <code>{message.chat.id}</code>"""

    rate_limit_per_hour = await db.get_chat_parameter(message.chat.id, "max_requests_per_hour")
    request_count = await db.get_request_count(message.chat.id, datetime.timedelta(hours=1))
    quota_text = "не ограничен" if rate_limit_per_hour == 0 else f"{request_count}/{rate_limit_per_hour}"

    text_to_send += f"\n📊 <b>Лимит запросов в час:</b> <i>{quota_text}</i>"

    if current_endpoint not in ["openai", "google"]:
        text_to_send += ("\n⚠️ <b>Неизвестное значение параметра <code>endpoint</code></b>. Значительная часть функций "
                         "бота недоступна.")

    reply = await message.reply(text_to_send)

    if current_endpoint == "google":
        token_count = await api.google.count_tokens_for_chat(message)
        text_to_send = text_to_send.replace("⏱ Секунду...", f"{token_count} токенов")
        await reply.edit_text(text_to_send)
