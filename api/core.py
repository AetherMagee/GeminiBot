from aiogram.types import Message

import api.google
import api.openai
import db


async def generate_response(message: Message) -> str:
    endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    if endpoint == "google":
        return await api.google.generate_response(message)
    elif endpoint == "openai":
        return await api.openai.generate_response(message)
    else:
        raise ValueError("what.")
