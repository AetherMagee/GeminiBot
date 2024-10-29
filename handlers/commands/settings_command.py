import difflib
from decimal import Decimal, ROUND_HALF_UP

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, ReactionTypeEmoji
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
    if s == "None" or s is None:
        return str(s)

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
    try:
        available_parameters = chat_configs["all_endpoints"] | chat_configs[chat_endpoint]
    except KeyError:
        available_parameters = chat_configs["all_endpoints"]

    async def get_current_value(chat_id: int, param: str):
        value = await db.get_chat_parameter(chat_id, param)
        if isinstance(value, Decimal):
            value = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if available_parameters[param]["private"] and isinstance(value, str):
            value = obfuscate_string(value)

        return value

    if len(command) == 1:
        text = "⚙️ <b>Доступные параметры бота:</b> \n"

        have_separated = False
        for parameter in available_parameters.keys():
            if available_parameters[parameter]["advanced"] and not show_advanced:
                continue

            if parameter not in chat_configs["all_endpoints"] and not have_separated:
                text += "\n"
                have_separated = True

            current_value = await get_current_value(message.chat.id, parameter)
            text += f"\n<code>{parameter}</code> - {current_value} "

        text += ("\n\n❔ <b>Для подробностей по параметру:</b> /settings <i>[параметр]</i>\n💾 <b>Установить новое "
                 "значение:</b> /set <i>[параметр] [значение]</i>")

        await message.reply(text)
    else:
        requested_parameter = command[1].lower()

        if requested_parameter not in available_parameters.keys():
            await message.reply("❌ <b>Неизвестный параметр</b>")
            return

        current_value = await get_current_value(message.chat.id, requested_parameter)

        try:
            default_value = available_parameters[requested_parameter]['default_value'].replace("\'", "")
        except AttributeError:
            default_value = str(available_parameters[requested_parameter]['default_value'])

        text = f"⚙️ <b>Параметр</b> <code>{requested_parameter}</code>:\n"
        text += f"<i>{available_parameters[requested_parameter]['description']}</i>\n\n"
        text += "❔ <b>Значения:</b> \n"
        text += f"<b>Нынешнее: <i>{current_value}</i></b>"
        if default_value != "None":
            text += f"\nСтандартное: {default_value}"

        _value_range = available_parameters[requested_parameter]['accepted_values']
        if isinstance(_value_range, range):
            accepted_values = f"{_value_range.start}-{_value_range.stop}"
        elif isinstance(_value_range, FloatRange):
            accepted_values = f"{_value_range[0]}—{_value_range[-1]}, шаг {round(_value_range[1] - _value_range[0], 2)}"
        else:
            try:
                accepted_values = ", ".join(_value_range)
            except TypeError:
                accepted_values = "True, False"

        if _value_range:
            text += f"\nДопустимые: {accepted_values}"

        if available_parameters[requested_parameter]["protected"]:
            text += "\n\n⚠️ <b>Этот параметр защищён - его могут менять только администраторы бота.</b>"

        await message.reply(text, disable_web_page_preview=True)


async def validate_and_set_parameter(chat_id: int, parameter_name: str, value: str, user_id: int) -> str or None:
    # Fetch the chat's endpoint
    chat_endpoint = await db.get_chat_parameter(chat_id, "endpoint")
    try:
        available_parameters = chat_configs["all_endpoints"] | chat_configs[chat_endpoint]
    except KeyError:
        available_parameters = chat_configs["all_endpoints"]

    # Verify parameter existence
    if parameter_name not in available_parameters.keys():
        matching_parameters = [param for param in available_parameters.keys() if param.startswith(parameter_name)]
        if len(matching_parameters) == 1:
            parameter_name = matching_parameters[0]
        elif not matching_parameters:
            return "❌ <b>Неизвестный параметр.</b>"

    # Check if the parameter is protected
    if available_parameters[parameter_name]["protected"] and user_id not in ADMIN_IDS:
        return ("❌ <b>У вас нет доступа к этому параметру. Свяжитесь с администратором бота, если хотите его "
                "изменить.</b>")

    # Handle type conversions
    parameter_type = available_parameters[parameter_name]["type"]
    try:
        if parameter_type == "integer":
            value = int(value)
        elif parameter_type == "decimal":
            value = float(value)
        elif parameter_type == "boolean":
            value = value.lower() in ["true", "1"]
    except ValueError:
        return "❌ <b>Недопустимое значение для параметра.</b>"

    # Validate against accepted values
    accepted_values = available_parameters[parameter_name]['accepted_values']
    if accepted_values and value not in accepted_values:
        if isinstance(accepted_values, (range, FloatRange)):
            if not (accepted_values.start <= value <= accepted_values.stop):
                return "❌ <b>Недопустимое значение для параметра.</b>"
        else:
            matching_values = difflib.get_close_matches(value, accepted_values, 1, 0.4)
            if matching_values:
                return f"Может быть, вы имели в виду <code>{matching_values[0]}</code>?"

    # Set the parameter in the database
    await db.set_chat_parameter(chat_id, parameter_name, value)


async def set_command(message: Message) -> None:
    await log_command(message)
    command = message.text.split(" ", maxsplit=2)

    if len(command) < 3:
        await message.reply("❌ <b>Недостаточно аргументов.</b>")
        return

    parameter_name = command[1].lower()
    value = command[2]
    chat_id = message.chat.id
    user_id = message.from_user.id

    result_msg = await validate_and_set_parameter(chat_id, parameter_name, value, user_id)
    if not result_msg:
        await message.react([ReactionTypeEmoji(emoji="👌")])
        return
    await message.reply(result_msg)


async def handle_private_setting(message: Message):
    global pending_sets

    if message.from_user.id not in pending_sets.keys():
        logger.warning(f"Was just called but the ID ({message.from_user.id}) is not in the pending list.")
        await message.reply("❌ <b>Произошёл непредвиденный сбой.</b>")
        return

    pending_set = pending_sets[message.from_user.id]

    if not pending_set[2]:
        await bot.send_message(message.from_user.id,
                               f"<b>Пожалуйста, отправьте сюда новое значение параметра <code>{pending_set[1]}</code"
                               f">. Оно будет установлено в чате с идентификатором {pending_set[0]}</b>\n<i>(его "
                               f"можно проверить командой /status в целевом чате)</i>")
        pending_set[2] = True
        return

    if pending_set[1] == "null" or pending_set[1] == "none":
        pending_set[1] = None

    await db.set_chat_parameter(pending_set[0], pending_set[1], message.text)
    await message.reply("✅ <b>Значение установлено!</b>")

    try:
        await bot.edit_message_text("✅ <b>Значение установлено!</b>", chat_id=pending_set[0], message_id=pending_set[3])
    except TelegramBadRequest:
        logger.warning(f"Failed to edit message {pending_set[3]} at {pending_set[0]}")

    pending_sets.pop(message.from_user.id)
