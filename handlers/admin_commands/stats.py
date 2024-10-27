from aiogram.types import Message
from loguru import logger

import db.statistics as stats
from main import ADMIN_IDS
from utils import get_entity_title, log_command


async def stats_command(message: Message):
    await log_command(message)

    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        # Get various statistics
        daily_active_count, _ = await stats.get_active_users(1)
        weekly_active_count, _ = await stats.get_active_users(7)
        monthly_active_count, _ = await stats.get_active_users(30)

        daily_gens = await stats.get_generation_counts(1)
        weekly_gens = await stats.get_generation_counts(7)

        total_tokens, top_chats = await stats.get_token_stats()
        tokens_last_24h = await stats.get_tokens_consumed(1)

        top_users = await stats.get_top_users(30)

        # Format the response
        response = f"""👥 <b>Активные пользователи</b>
• День: {daily_active_count}
• Неделя: {weekly_active_count}
• Месяц: {monthly_active_count}

🤖 <b>Обработано генераций</b>
• Последние 24ч: {daily_gens}
• Последние 7д: {weekly_gens}

💭 <b>Использовано токенов</b>
• Всего: {total_tokens:,}
• Последние 24ч: {tokens_last_24h:,}

💬 <b>Топ 5 чатов по потреблению токенов</b>:
"""

        for i, chat in enumerate(top_chats, 1):
            chat_title = await get_entity_title(chat['chat_id'])
            response += f"{i}. {chat_title} ({chat['chat_id']}): {chat['tokens']:,} tokens\n"

        response += "\n👤 <b>Самые активные пользователи (кол-во генераций, 30д)</b>\n"
        for i, user in enumerate(top_users, 1):
            user_name = await get_entity_title(user['user_id'])
            response += f"{i}. {user_name} ({user['user_id']}): {user['generations']} generations\n"

        await message.reply(response)

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        await message.reply("❌ Не удалось собрать статистику")
