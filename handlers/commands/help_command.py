import os

from aiogram.types import Message

from utils import log_command

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def help_command(message: Message):
    await log_command(message)

    if message.from_user.id != message.chat.id and bot_username not in message.text:
        return

    help_text = """<b>Команды бота:</b>
<b>/help</b> - Показать это сообщение
<b>/status</b> - Проверить состояние бота
<b>/settings</b> - Открыть настройки бота
<b>/raw</b> - Отправить запрос без памяти и системных инструкций

<b>Управление памятью:</b>
<b>/reset или /clear</b> - Очистить память бота
<b>/forget [ответом]</b> - Удалить определённое сообщение из памяти бота
<b>/replace {текст} [ответом]</b> - Заменить сообщение в памяти бота
<b>/system {текст}</b> - Добавить в память бота новую системную инструкцию
"""
    await message.reply(help_text)
