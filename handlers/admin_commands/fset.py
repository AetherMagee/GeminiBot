from aiogram.types import Message, ReactionTypeEmoji

from handlers.commands.settings_command import validate_and_set_parameter
from main import ADMIN_IDS
from utils import get_message_text, log_command


async def fset_command(message: Message) -> None:
    await log_command(message)

    text = await get_message_text(message)
    args = text.split(" ", 4)

    if len(args) != 4:
        await message.reply("❌ <b>Неверное число аргументов</b>")
        return

    chat_id = int(args[1])
    parameter_name = args[2].lower()
    value = args[3]

    result_msg = await validate_and_set_parameter(chat_id, parameter_name, value, ADMIN_IDS[0])
    if not result_msg:
        await message.react([ReactionTypeEmoji(emoji="👌")])
        return
    await message.reply(result_msg)
