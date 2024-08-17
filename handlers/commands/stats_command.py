import datetime
import asyncio
from collections import defaultdict

from aiogram.types import Message

import db.shared as dbs
from main import ADMIN_IDS, bot

lock: dict = {}
global_stats_command = """WITH tbl AS
  (SELECT table_schema,
          TABLE_NAME
   FROM information_schema.tables
   WHERE TABLE_NAME not like 'chat_config'
     AND table_schema in ('public'))
SELECT table_schema,
       TABLE_NAME,
       (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, TABLE_NAME), FALSE, TRUE, '')))[1]::text::int AS rows_n
FROM tbl
ORDER BY rows_n DESC;"""


async def stats_command(message: Message) -> None:
    lock.setdefault(message.chat.id, False)
    if lock[message.chat.id]:
        await message.reply("❌ <b>Пожалуйста, подождите перед запуском этой команды снова.</b>")
        return
    lock[message.chat.id] = True

    san_chat_id = await dbs.sanitize_chat_id(message.chat.id)
    async with dbs.pool.acquire() as conn:
        global_stats = await conn.fetch(global_stats_command) if message.from_user.id in ADMIN_IDS else None
        chat_messages = await conn.fetch(
            f"SELECT umid, sender_id, timestamp FROM messages{san_chat_id} WHERE sender_id NOT IN (0, 727)")

    current_time = datetime.datetime.now()
    chat_messages_last_hour = sum(
        1 for db_message in chat_messages if (current_time - db_message['timestamp']).total_seconds() <= 3600)

    text = (f"📊 <b>Статистика бота в этом чате:</b>\n\n"
            f"<b>Всего сообщений:</b> <i>{len(chat_messages)}</i>\n"
            f"<b>За последний час:</b> <i>{chat_messages_last_hour}</i>\n")

    if message.chat.id != message.from_user.id:
        chat_messages_by_user = defaultdict(int)
        for db_message in chat_messages:
            chat_messages_by_user[db_message['sender_id']] += 1

        top_users = sorted(chat_messages_by_user.items(), key=lambda item: item[1], reverse=True)[:5]
        top_users_text = "\n".join(
            f"{(await bot.get_chat_member(chat_id=message.chat.id, user_id=user[0])).user.first_name} - {user[1]}"
            for user in top_users)
        text += f"\n<b>Топ активных пользователей:</b>\n<i>{top_users_text}</i>"

    if global_stats:
        total_processed_messages = sum(entry['rows_n'] for entry in global_stats)
        top_chats_text = "\n".join(
            f"{chat['table_name'].replace('messages', '').replace('_', '')} - {chat['rows_n']}" for chat in
            global_stats[:5])
        text += f"\n========\n\n<b>Всего сообщений в бд:</b> <i>{total_processed_messages}</i>\n<b>Топ чатов:</b> \n<i>{top_chats_text}</i>"

    await message.reply(text)

    await asyncio.create_task(unlock_after_delay(message.chat.id))


async def unlock_after_delay(chat_id: int, delay: int = 5) -> None:
    await asyncio.sleep(delay)
    lock[chat_id] = False
