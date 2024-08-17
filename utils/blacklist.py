from aiogram.filters import BaseFilter
from aiogram.types import Message

import db


class BlacklistFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return not await db.is_blacklisted(message.chat.id) and not await db.is_blacklisted(message.from_user.id)
