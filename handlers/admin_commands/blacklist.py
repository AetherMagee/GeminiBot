from aiogram.types import Message, ReactionTypeEmoji

import db
from utils import get_message_text, log_command


async def blacklist_command(message: Message):
    await log_command(message)

    text = await get_message_text(message)
    target = int(text.split(" ", maxsplit=1)[1])

    await db.add_to_blacklist(target)

    await message.react([ReactionTypeEmoji(emoji="👌")])


async def unblacklist_command(message: Message):
    await log_command(message)

    text = await get_message_text(message)
    target = int(text.split(" ", maxsplit=1)[1])

    await db.remove_from_blacklist(target)

    await message.react([ReactionTypeEmoji(emoji="👌")])
