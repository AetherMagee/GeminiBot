from aiogram.types import Message

import db
from utils import log_command


async def prune_command(message: Message):
    await log_command(message)

    args = message.text.split(' ')
    if len(args) < 3:
        await message.reply("❌ <b>Использование:</b> /prune [chat_id] [days], где days - максимальный возраст "
                            "сообщения в днях.\nТ.е. при days=14, все сообщения старше 14 дней будут удалены.\n\n\"*\" "
                            "вместо айди чата запустит очистку всей БД.\n\n⚠️<b> Эта операция необратима.</b>")
        return

    if args[1] != '*':
        target_chat_id = int(args[1])
    else:
        target_chat_id = None
    cutoff_days = int(args[2])

    response = await message.reply(f"🕔 <b>Удаление сообщений, отправленных ранее {cutoff_days} дн. назад...</b>")
    result = await db.delete_old_messages(cutoff_days, target_chat_id)

    await response.edit_text(
        f"✅ <b>Удалено <code>{result['deleted_count']}</code> сообщений <i>({result['freed_space']})</i></b>")
