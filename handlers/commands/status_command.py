from aiogram.types import Message

import api.google
import db


async def status_command(message: Message):
    try:
        messages_count = len(await db.get_messages(message.chat.id))  # inefficient and slow but idgaf
    except TypeError:
        messages_count = 0

    messages_limit = await db.get_chat_parameter(message.chat.id, "message_limit")

    text_to_send = f"""✅ <b>Бот активен!</b>
💬 <b>Память:</b> {messages_count}/{messages_limit} сообщений <i>(⏱ Секунду...)</i>
🆔 <b>ID чата:</b> <code>{message.chat.id}</code>"""

    reply = await message.reply(text_to_send)

    token_count = await api.google.count_tokens_for_chat(message.chat.id)
    text_to_send = text_to_send.replace("⏱ Секунду...", f"токенов: {token_count}")
    await reply.edit_text(text_to_send)
