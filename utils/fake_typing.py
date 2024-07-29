import asyncio

from aiogram.enums import ChatAction

from main import bot


async def simulate_typing(chat_id: int) -> None:
    """
    Simulates typing action for a given chat id.
    Should only be called as an asyncio task.
    """

    loops = 0
    while loops < 10:
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(4)
        loops += 1
