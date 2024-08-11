import difflib
import itertools
import traceback
from typing import List

from aiogram.types import Message, ReactionTypeEmoji
from loguru import logger

import db
from main import bot, ADMIN_IDS
from utils import log_command
from utils.definitions import chat_configs
from utils.frange import FloatRange


async def settings_command(message: Message) -> None:
    await log_command(message)
    command = message.text.split(" ", maxsplit=1)
    chat_endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    show_advanced = await db.get_chat_parameter(message.chat.id, "show_advanced_settings")
    available_parameters = chat_configs["all_endpoints"] | chat_configs[chat_endpoint]
    if len(command) == 1:
        text = "<b>Доступные параметры бота:</b> \n"

        for parameter in available_parameters.keys():
            if available_parameters[parameter]["advanced"] and not show_advanced:
                continue

            if parameter not in chat_configs["all_endpoints"] and "===" not in text:
                text += "\n<b>============</b>"
            text += f"\n<code>{parameter}</code> - {await db.get_chat_parameter(message.chat.id, parameter)} "

        text += ("\n\n<b>Для подробностей по параметру:</b> /settings [параметр]\n<b>Установить новое значение:</b> "
                 "/set [параметр] [значение]")

        await message.reply(text)
    else:
        requested_parameter = command[1].lower()

        if requested_parameter not in available_parameters.keys():
            await message.reply("❌ <b>Неизвестный параметр</b>")
            return

        current_value = await db.get_chat_parameter(message.chat.id, requested_parameter)
        try:
            default_value = available_parameters[requested_parameter]['default_value'].replace("\'", "")
        except AttributeError:
            default_value = str(available_parameters[requested_parameter]['default_value'])

        text = f"<b>Параметр</b> <code>{requested_parameter}</code>:\n"
        text += f"<i>{available_parameters[requested_parameter]['description']}</i>\n"
        text += "<b>Значения:</b> \n"
        text += f"Нынешнее: {current_value} | "
        text += f"Стандартное: {default_value} | "

        _value_range = available_parameters[requested_parameter]['accepted_values']
        if isinstance(_value_range, range):
            accepted_values = f"{_value_range.start}-{_value_range.stop}"
        elif isinstance(_value_range, FloatRange):
            accepted_values = f"{_value_range[0]}—{_value_range[-1]}, шаг {round(_value_range[1] - _value_range[0], 2)}"
        else:
            try:
                accepted_values = ", ".join(_value_range)
            except Exception:
                accepted_values = "True, False"

        text += f"Допустимые: {accepted_values}"

        if available_parameters[requested_parameter]["protected"]:
            text += "\n⚠️ <b>Этот параметр защищён - его могут менять только администраторы бота.</b>"

        await message.reply(text)


async def set_command(message: Message) -> None:
    await log_command(message)
    if message.chat.id != message.from_user.id and message.from_user.id not in ADMIN_IDS:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ <b>Параметры могут менять только администраторы.</b>")
            return

    command = message.text.split(" ", maxsplit=2)
    if len(command) < 2:
        await message.reply("❌ <b>Недостаточно аргументов.</b>")

    requested_parameter = command[1].lower()
    chat_endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    available_parameters = chat_configs["all_endpoints"] | chat_configs[chat_endpoint]

    if requested_parameter not in available_parameters.keys():
        await message.reply("❌ <b>Неизвестный параметр.</b>")
        return

    requested_value = command[2].lower()
    if available_parameters[requested_parameter]["type"] == "integer":
        try:
            requested_value = int(requested_value)
        except ValueError:
            requested_value = None
    elif available_parameters[requested_parameter]["type"] == "decimal":
        try:
            requested_value = float(requested_value)
        except ValueError:
            requested_value = None
    elif available_parameters[requested_parameter]["type"] == "boolean":
        try:
            if requested_value == "true" or requested_value == "1":
                requested_value = True
            elif requested_value == "false" or requested_value == "0":
                requested_value = False

        except ValueError:
            requested_value = None

    if requested_value not in available_parameters[requested_parameter]['accepted_values']:
        reply_text = "❌ <b>Недопустимое значение для параметра.</b> "
        if available_parameters[requested_parameter]["type"] == "text":
            probable_value = difflib.get_close_matches(requested_value,
                                                       available_parameters[requested_parameter]['accepted_values'],
                                                       1,
                                                       0.4)
            if len(probable_value) > 0:
                reply_text += f"Может быть, вы имели в виду <code>{probable_value[0]}</code>?"
        await message.reply(reply_text)
        return

    if available_parameters[requested_parameter]["protected"]:
        if message.from_user.id not in ADMIN_IDS:
            await message.reply("❌ <b>У вас нет доступа к этому параметру. Свяжитесь с администратором бота, "
                                "если хотите его изменить.</b>")
            return

    try:
        await db.set_chat_parameter(message.chat.id, requested_parameter, requested_value)
        await message.react([ReactionTypeEmoji(emoji="👌")])
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        await message.reply("❌ <b>Непредвиденная ошибка при установке параметра.</b>")
        return
