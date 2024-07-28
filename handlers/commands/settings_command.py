import traceback

from aiogram.types import Message
from loguru import logger

import db
from main import bot
from utils.definitions import chat_configs


async def settings_command(message: Message) -> None:
    command = message.text.split(" ", maxsplit=1)
    if len(command) == 1:
        text = "*Доступные параметры бота:* \n"
        for parameter in chat_configs.keys():
            text += f"\n`{parameter}` (_{chat_configs[parameter]['description']}_) - {await db.get_chat_parameter(message.chat.id, parameter)} "

        text += ("\n\n*Для подробностей по параметру:* /settings \\[параметр]\n*Установить новое значение:* /set \\["
                 "параметр] \\[значение]")

        await message.reply(text)
    else:
        requested_parameter = command[1].lower()
        if requested_parameter not in chat_configs.keys():
            await message.reply("❌ *Неизвестный параметр*")
            return

        current_value = await db.get_chat_parameter(message.chat.id, requested_parameter)

        text = f"*Параметр* `{requested_parameter}`:\n"
        text += f"_{chat_configs[requested_parameter]['description']}_\n"
        text += "*Значения:* \n"
        text += f"Нынешнее: {current_value} | "
        text += f"Стандартное: {chat_configs[requested_parameter]['default_value']} | "
        _value_range = chat_configs[requested_parameter]['accepted_values']
        if isinstance(_value_range, range):
            accepted_values = f"{_value_range.start}-{_value_range.stop}"
        else:
            accepted_values = ", ".join(_value_range)
        text += f"Допустимые: {accepted_values}"
        await message.reply(text)


async def set_command(message: Message) -> None:
    if message.chat.id != message.from_user.id:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ *Параметры могут менять только администраторы.*")
            return

    command = message.text.split(" ", maxsplit=2)
    if len(command) < 2:
        await message.reply("❌ *Недостаточно аргументов.*")

    requested_parameter = command[1].lower()
    if requested_parameter not in chat_configs.keys():
        await message.reply("❌ *Неизвестный параметр.*")
        return

    requested_value = command[2].lower()
    if chat_configs[requested_parameter]["type"] == "integer":
        try:
            requested_value = int(requested_value)
        except ValueError:
            requested_value = None

    if requested_value not in chat_configs[requested_parameter]['accepted_values']:
        await message.reply("❌ *Недопустимое значение для параметра.*")
        return

    try:
        await db.set_chat_parameter(message.chat.id, requested_parameter, requested_value)
        await message.reply("✅ *Параметр установлен.*")
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        await message.reply("❌ *Непредвиденная ошибка при установке параметра.*")
        return
