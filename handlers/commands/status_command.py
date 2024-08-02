from aiogram.types import Message

import api.google
import db
from utils import log_command


async def status_command(message: Message):
    log_command(message)
    messages = await db.get_messages(message.chat.id)

    messages_limit = await db.get_chat_parameter(message.chat.id, "message_limit")
    current_model = await db.get_chat_parameter(message.chat.id, "model")

    text_to_send = f"""✅ <b>Бот активен!</b>
💬 <b>Память:</b> {len(messages)}/{messages_limit} сообщений <i>(⏱ Секунду...)</i>
✨ <b>Модель:</b> <i>{current_model}</i>
🆔 <b>ID чата:</b> <code>{message.chat.id}</code>"""

    reply = await message.reply(text_to_send)

    token_count = await api.google.count_tokens_for_chat(messages, await db.get_chat_parameter(message.chat.id, "model"))
    text_to_send = text_to_send.replace("⏱ Секунду...", f"токенов: {token_count}")
    await reply.edit_text(text_to_send)
