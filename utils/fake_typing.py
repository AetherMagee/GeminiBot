import asyncio
from contextlib import asynccontextmanager

from aiogram.enums import ChatAction

from main import bot

_typing_tasks = {}
_typing_counters = {}
_typing_locks = {}


@asynccontextmanager
async def simulate_typing(chat_id: int):
    """
    Simulates typing action for a given chat id.
    Ensures only one typing simulator is active per chat.
    """
    if chat_id not in _typing_locks:
        _typing_locks[chat_id] = asyncio.Lock()

    async with _typing_locks[chat_id]:
        # Increment the counter
        _typing_counters[chat_id] = _typing_counters.get(chat_id, 0) + 1

        if chat_id not in _typing_tasks:
            # Start the typing simulation
            stop_event = asyncio.Event()
            typing_task = asyncio.create_task(_simulate_typing_task(chat_id, stop_event))
            _typing_tasks[chat_id] = (typing_task, stop_event)

    try:
        yield
    finally:
        async with _typing_locks[chat_id]:
            # Decrement the counter
            _typing_counters[chat_id] -= 1
            if _typing_counters[chat_id] <= 0:
                # Stop the typing simulation
                typing_task, stop_event = _typing_tasks.pop(chat_id)
                stop_event.set()
                await typing_task
                _typing_counters.pop(chat_id)
                _typing_locks.pop(chat_id)


async def _simulate_typing_task(chat_id: int, stop_event: asyncio.Event):
    try:
        while not stop_event.is_set():
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4)
            except asyncio.TimeoutError:
                pass
    except Exception:
        pass
