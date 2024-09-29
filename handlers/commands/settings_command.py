import asyncio
import difflib
import os
import traceback

from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, Message, ReactionTypeEmoji
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

import db
from main import ADMIN_IDS, bot
from utils import log_command
from utils.definitions import chat_configs
from utils.frange import FloatRange

pending_sets = {
    # user_id: [target_chat, target_param, has_notified]
}


def obfuscate_string(s: str) -> str:
    prefix = ""
    if s.startswith("https://"):
        prefix = "https://"
        s = s[len("https://"):]  # Remove the prefix for obfuscation

    if len(s) <= 10:
        obfuscated = '*' * len(s)
    else:
        obfuscated = s[:4] + '*' * (len(s) - 8) + s[-4:]

    return prefix + obfuscated


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

            current_value = await db.get_chat_parameter(message.chat.id, parameter)
            if available_parameters[parameter]["private"] and isinstance(current_value, str):
                current_value = obfuscate_string(current_value)
            text += f"\n<code>{parameter}</code> - {current_value} "

        text += ("\n\n<b>Для подробностей по параметру:</b> /settings [параметр]\n<b>Установить новое значение:</b> "
                 "/set [параметр] [значение]")

        await message.reply(text)
    else:
        requested_parameter = command[1].lower()

        if requested_parameter not in available_parameters.keys():
            await message.reply("❌ <b>Неизвестный параметр</b>")
            return

        current_value = await db.get_chat_parameter(message.chat.id, requested_parameter)
        if available_parameters[requested_parameter]["private"]:
            current_value = obfuscate_string(current_value)

        try:
            default_value = available_parameters[requested_parameter]['default_value'].replace("\'", "")
        except AttributeError:
            default_value = str(available_parameters[requested_parameter]['default_value'])

        text = f"<b>Параметр</b> <code>{requested_parameter}</code>:\n"
        text += f"<i>{available_parameters[requested_parameter]['description']}</i>\n"
        text += "<b>Значения:</b> \n"
        text += f"Нынешнее: {current_value}"
        if default_value != "None":
            text += f" | Стандартное: {default_value}"

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

        if _value_range:
            text += f" | Допустимые: {accepted_values}"

        if available_parameters[requested_parameter]["protected"]:
            text += "\n⚠️ <b>Этот параметр защищён - его могут менять только администраторы бота.</b>"

        await message.reply(text)


async def set_command(message: Message) -> None:
    global pending_sets

    await log_command(message)

    # Check for administrator
    if message.chat.id != message.from_user.id and message.from_user.id not in ADMIN_IDS:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await message.reply("❌ <b>Параметры могут менять только администраторы.</b>")
            return

    # Check argument count
    command = message.text.split(" ", maxsplit=2)
    if len(command) < 2:
        await message.reply("❌ <b>Недостаточно аргументов.</b>")

    # Validate target parameter
    requested_parameter = command[1].lower()
    chat_endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")
    available_parameters = chat_configs["all_endpoints"] | chat_configs[chat_endpoint]

    if requested_parameter not in available_parameters.keys():
        await message.reply("❌ <b>Неизвестный параметр.</b>")
        return

    # Check if the parameter is protected
    if available_parameters[requested_parameter]["protected"]:
        if message.from_user.id not in ADMIN_IDS:
            await message.reply("❌ <b>У вас нет доступа к этому параметру. Свяжитесь с администратором бота, "
                                "если хотите его изменить.</b>")
            return

    # Check if it's private
    if available_parameters[requested_parameter]["private"] and message.from_user.id != message.chat.id:
        pending_sets[message.from_user.id] = [
            message.chat.id,
            requested_parameter,
            False
        ]

        await message.reply("👋 <b>Давайте перейдём в личные сообщения, чтобы установить этот параметр, не раскрывая "
                            "его другим.</b>")
        await asyncio.sleep(1)
        try:
            await handle_private_setting(message)
        except TelegramForbiddenError:
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(
                text="Начать диалог",
                url=f"https://t.me/{os.getenv('BOT_USERNAME')}")
            )
            await message.reply("<b>Похоже, у нас с вами ещё нет личного диалога. Нажмите на кнопку ниже, чтобы это "
                                "исправить.</b>", reply_markup=builder.as_markup())
        return

    # Get target parameter's accepted value type
    try:
        requested_value = command[2].lower()
    except IndexError:
        await message.reply("❌ <b>Вы не ввели значение параметра.</b>")
        return

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

    # Validate target value
    accepted_values = available_parameters[requested_parameter]['accepted_values']
    if accepted_values:
        if isinstance(accepted_values, range):
            accepted_values = range(accepted_values.start,
                                    accepted_values.stop + 1)
        if requested_value not in accepted_values:
            if message.from_user.id not in ADMIN_IDS:
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
            else:
                await message.reply("⚠️ <b>Значение параметра вне списка разрешённых, но так как вы - администратор бота, "
                                    "оно всё равно будет установлено.</b>")

    # Set the parameter
    try:
        await db.set_chat_parameter(message.chat.id, requested_parameter, requested_value)
        await message.react([ReactionTypeEmoji(emoji="👌")])
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        await message.reply("❌ <b>Непредвиденная ошибка при установке параметра.</b>")
        return


async def handle_private_setting(message: Message):
    global pending_sets

    if message.from_user.id not in pending_sets.keys():
        await message.reply("❌ <b>Произошёл непредвиденный сбой.</b>")
        return

    pending_set = pending_sets[message.from_user.id]

    if not pending_set[2]:
        await bot.send_message(message.from_user.id,
                               f"<b>Пожалуйста, отправьте сюда новое значение параметра <code>{pending_set[1]}</code>. Оно будет установлено в чате с идентификатором {pending_set[0]}</b>\n<i>(его можно проверить командой /status в целевом чате)</i>")
        pending_set[2] = True
        return

    await db.set_chat_parameter(pending_set[0], pending_set[1], message.text)
    await message.reply("✅ <b>Значение установлено!</b>")

    pending_sets.pop(message.from_user.id)
