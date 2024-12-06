import time

import tiktoken
from loguru import logger

import db
from api.google import format_message_for_prompt
from api.prompt import get_system_prompt


async def count_tokens(chat_id: int) -> int:
    all_messages_list = [await format_message_for_prompt(message) for message in await db.get_messages(chat_id)]
    text = "\n".join(all_messages_list)
    text = await get_system_prompt() + text

    load_encoding_start = time.perf_counter()
    try:
        encoding = tiktoken.encoding_for_model(await db.get_chat_parameter(chat_id, "o_model"))
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    load_encoding_end = time.perf_counter()
    if load_encoding_end - load_encoding_start > 0.5:
        logger.warning(f"Loading an encoding took {round(load_encoding_end - load_encoding_start, 2)}s")

    encode_start = time.perf_counter()
    encoded = encoding.encode_ordinary(text)
    encode_end = time.perf_counter()

    if encode_end - encode_start > 0.5:
        logger.warning(f"Encoding took {round(encode_end - encode_start, 2)}s")

    return len(encoded)
