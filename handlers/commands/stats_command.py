import datetime
import asyncio

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
    """Probably the most gore function yet."""

    global lock

    if message.chat.id not in lock.keys():
        lock[message.chat.id] = False

    if lock[message.chat.id]:
        await message.reply("❌ <b>Пожалуйста, подождите перед запуском этой команды снова.</b>")
        return

    lock[message.chat.id] = True

    san_chat_id = await dbs.sanitize_chat_id(message.chat.id)
    async with dbs.pool.acquire() as conn:
        if message.from_user.id in ADMIN_IDS:
            global_stats = await conn.fetch(global_stats_command)
        else:
            global_stats = None
        chat_messages = await conn.fetch(
            f"SELECT umid, sender_id, timestamp FROM messages{san_chat_id} WHERE sender_id NOT IN (0, 727)")

    chat_messages_total = len(chat_messages)

    chat_messages_last_hour = 0
    for db_message in chat_messages:
        time_diff = datetime.datetime.now() - db_message['timestamp']
        if not time_diff.total_seconds() > 3600:
            chat_messages_last_hour += 1

    text = f"""📊 <b>Статистика бота в этом чате</b>

<b>Всего сообщений обработано:</b> <i>{chat_messages_total}</i>
<b>За последний час:</b> <i>{chat_messages_last_hour}</i>
"""
    if not message.chat.id == message.from_user.id:
        chat_messages_by_user = {}
        for db_message in chat_messages:
            if not db_message['sender_id'] in chat_messages_by_user.keys():
                chat_messages_by_user[db_message['sender_id']] = 1
            else:
                chat_messages_by_user[db_message['sender_id']] += 1

        chat_messages_by_user = sorted(chat_messages_by_user.items(), key=lambda item: item[1], reverse=True)
        top_users = chat_messages_by_user[:5]
        top_users_text = ""
        for user in top_users:
            member = await bot.get_chat_member(chat_id=message.chat.id, user_id=user[0])
            top_users_text += f"{member.user.first_name} - {user[1]}\n"
        text += f"\n<b>Самые активные в чате:</b>\n<i>{top_users_text}</i>"

    if global_stats:
        total_processed_messages = 0
        for entry in global_stats:
            total_processed_messages += entry['rows_n']

        top_chats = global_stats[:5]
        top_chats_text = ""
        for chat in top_chats:
            top_chats_text += f"{chat['table_name'].replace('messages', '').replace('_', '')} - {chat['rows_n']}\n"

        text += (f"\n========\n\n<b>Всего сообщений в БД:</b> <i>{total_processed_messages}</i>\n<b>Топ чатов:</b> "
                 f"\n<i>{top_chats_text}</i>")

    await message.reply(text)

    await asyncio.sleep(5)

    lock[message.chat.id] = False
