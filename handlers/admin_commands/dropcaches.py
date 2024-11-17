from aiogram.types import Message, ReactionTypeEmoji

import db
import utils


async def dropcaches_command(message: Message):
    await utils.log_command(message)

    db.chats.blacklist.is_blacklisted.cache_clear()
    db.chats.chat_config.get_chat_parameter.cache_clear()
    utils.usernames.get_entity_title.cache_clear()

    await message.react([ReactionTypeEmoji(emoji="👌")])
