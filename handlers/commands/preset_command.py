from aiogram.types import Message
from loguru import logger

import db
from main import ADMIN_IDS, bot
from utils import log_command
from utils.definitions import presets


async def preset_command(message: Message):
    await log_command(message)

    # Check for administrator
    if message.chat.id != message.from_user.id and message.from_user.id not in ADMIN_IDS:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ <b>Параметры могут менять только администраторы.</b>")
            return

    # Check argument count
    command = message.text.split(" ", maxsplit=1)
    if len(command) < 2:
        await message.reply(
            "❌ <b>Недостаточно аргументов.</b>\nИспользование команды: <i>/preset [название]</i>\nДоступные пресеты: "
            + ", ".join(presets.keys()))
        return

    target_preset = command[1].lower()
    if target_preset not in presets.keys():
        await message.reply("❌ <b>Неизвестный пресет.</b>")
        return

    endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    if endpoint == "openai":
        blacklisted_prefix = "g_"
    elif endpoint == "google":
        blacklisted_prefix = "o_"
    else:
        raise ValueError("what?")

    changed_params = {}
    for parameter, value in presets[target_preset].items():
        if parameter.startswith(blacklisted_prefix):
            continue

        if parameter == "endpoint" and message.from_user.id not in ADMIN_IDS:
            continue

        if await db.get_chat_parameter(message.chat.id, parameter) != value:
            await db.set_chat_parameter(message.chat.id, parameter, value)
            changed_params[parameter] = value

    text = f"✅ <b>Обновлено {len(changed_params)} параметров:</b>\n"
    for parameter, value in changed_params.items():
        text += f"<code>{parameter}</code> - <i>{value}</i>\n"

    await message.reply(text)


