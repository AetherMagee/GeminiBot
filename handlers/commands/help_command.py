import os

from aiogram.types import Message

from main import ADMIN_IDS
from utils import log_command

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def help_command(message: Message):
    await log_command(message)

    if message.from_user.id != message.chat.id and bot_username not in message.text:
        return

    help_text = """🤖 <b>Команды бота:</b>
<b>/help</b> - Показать это сообщение
<b>/status</b> - Проверить состояние бота
<b>/stats</b> - Посмотреть статистику чата
<b>/feedback <i>[текст]</i></b> - Отправить разработчикам вопрос или пожелание

⚙️ <b>Параметры:</b>
<b>/settings</b> - Открыть параметры бота
<b>/settings <i>[параметр]</i></b> - Увидеть подробности про определённый параметр
<b>/set <i>[параметр] [значение]</i></b> - Изменить параметр
<b>/preset <i>[название]</i></b> - Активировать заранее заготовленный набор настроек

💬 <b>Управление памятью:</b>
<b>/reset или /clear</b> - Очистить память бота
<b>/forget</b> - Удалить определённое сообщение из памяти бота. <i>Команда используется ответом на целевое сообщение.</i>
<b>/replace <i>{текст}</i></b> - Заменить сообщение в памяти бота. <i>Команда используется ответом на целевое сообщение.</i>
<b>/system <i>{текст}</i></b> - Добавить в память бота новую системную инструкцию
"""

    if message.from_user.id in ADMIN_IDS:
        help_text += """
🔧 <b>Команды администраторов бота:</b>
<b>/dropcaches</b> - Очистка всех кэшей
<b>/blacklist <i>[id]</i></b> - Добавить чат/пользователя в чёрный список
<b>/unblacklist <i>[id]</i></b> - Удалить чат/пользователя из чёрного списка
<b>/stats</b> - Показать статистику бота
<b>/sql <i>[-fetch] [команда]</i></b>- Выполнить сырой SQL-запрос
<b>/restart</b> - Перезагрузить бота
"""
    await message.reply(help_text)
