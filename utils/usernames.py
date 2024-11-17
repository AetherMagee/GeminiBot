from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from async_lru import alru_cache

from main import bot


@alru_cache
async def get_entity_title(target_id: int) -> str:
    try:
        chat = await bot.get_chat(target_id)
        if chat.type in ['group', 'supergroup']:
            return chat.title or str(target_id)
        elif chat.type == 'private':
            return f"{chat.first_name} {chat.last_name or ''}".strip()
        else:
            return str(target_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        return str(target_id)
