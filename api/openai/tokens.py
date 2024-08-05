import tiktoken

import db
from api.google import format_message_for_prompt

encoding = tiktoken.get_encoding("cl100k_base")


async def count_tokens(chat_id: int) -> int:
    all_messages_list = [await format_message_for_prompt(message) for message in await db.get_messages(chat_id)]
    text = "\n".join(all_messages_list)

    return len(encoding.encode(text))
