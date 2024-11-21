from aiogram.types import Message, ReactionTypeEmoji
from loguru import logger

from main import bot
from utils import log_command, get_message_text


async def directsend_command(message: Message):
    await log_command(message)
    text = await get_message_text(message)
    command = text.split(' ', maxsplit=2)

    if len(command) < 2:
        await message.reply("❌ <b>Использование: /directsend user_id content</b>")
        return

    try:
        target = int(command[1])

        if message.photo:
            caption = command[2] if len(command) > 2 else None
            photo = message.photo[-1]
            logger.info(f"Sending direct photo to {target}")
            await bot.send_photo(
                chat_id=target,
                photo=photo.file_id,
                caption=caption
            )
        else:
            if len(command) < 3:
                await message.reply("❌ <b>Использование: /directsend user_id content</b>")
                return

            logger.info(f"Sending direct message to {target}")
            await bot.send_message(
                chat_id=target,
                text=command[2]
            )

        await message.react([ReactionTypeEmoji(emoji="👌")])

    except Exception as e:
        logger.error(f"Error sending direct message: {e}")
        await message.reply(f"❌ {str(e)}")
