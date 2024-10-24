from aiogram.types import Message

import api.google
import api.openai
import db
from utils import log_command


async def status_command(message: Message):
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

    if current_endpoint not in ["openai", "google"]:
        text_to_send += ("\n⚠️ <b>Неизвестное значение параметра <code>endpoint</code></b>. Значительная часть функций "
                         "бота недоступна.")

    reply = await message.reply(text_to_send)

    if current_endpoint == "google":
        token_count = await api.google.count_tokens_for_chat(message)
        text_to_send = text_to_send.replace("⏱ Секунду...", f"{token_count} токенов")
        await reply.edit_text(text_to_send)
