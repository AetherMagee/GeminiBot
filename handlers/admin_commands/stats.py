import time
import traceback
from datetime import datetime, timedelta
from typing import List

from aiogram.types import Message
from loguru import logger

import db.statistics as stats
from main import ADMIN_IDS
from utils import get_entity_title


def sparkline(numbers: List[float]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    if not numbers:
        return ""
    mn, mx = min(numbers), max(numbers)
    extent = mx - mn
    if extent == 0:
        return bars[0] * len(numbers)
    return "".join(bars[int((n - mn) / extent * (len(bars) - 1))] for n in numbers)


async def stats_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        start_time = time.time()

        # Get all existing stats
        now = datetime.now()
        start_of_today = datetime.combine(now.date(), datetime.min.time())
        one_hour_ago = now - timedelta(hours=1)

        daily_active_count, _ = await stats.get_active_users(1)
        weekly_active_count, _ = await stats.get_active_users(7)
        monthly_active_count, _ = await stats.get_active_users(30)

        daily_gens = await stats.get_generation_counts_period(start_of_today)
        hourly_gens = await stats.get_generation_counts_period(one_hour_ago)
        weekly_gens = await stats.get_generation_counts(7)
        total_gens = await stats.get_generation_counts_period(datetime.min)

        total_tokens, top_chats = await stats.get_token_stats()
        tokens_last_24h = await stats.get_tokens_consumed(1)
        tokens_today = await stats.get_tokens_consumed_period(start_of_today)
        tokens_last_hour = await stats.get_tokens_consumed_period(one_hour_ago)

        top_users = await stats.get_top_users(30)

        # Get new enhanced stats
        hourly_counts = await stats.get_hourly_stats(24)
        model_usage = await stats.get_model_usage(30)
        costs = await stats.calculate_costs(model_usage)

        # Get new cost statistics
        total_stats = await stats.get_total_cost_stats()
        all_time_costs = await stats.calculate_costs(total_stats['all_time'])
        last_30d_costs = await stats.calculate_costs(total_stats['last_30d'])

        # Get entity costs
        top_chats_costs = await stats.get_cost_stats_for_entities('chat', 5)
        top_users_costs = await stats.get_cost_stats_for_entities('user', 5)

        # Build enhanced response
        response = f"""📊 <b>Статистика бота</b> 

👥 <b>Активные пользователи</b>
• День: <b>{daily_active_count}</b>
• Неделя: <b>{weekly_active_count}</b>
• Месяц: <b>{monthly_active_count}</b>

🤖 <b>Обработано генераций</b>
• Всего: <b>{total_gens}</b>
• За неделю: <b>{weekly_gens}</b>
• Сегодня: <b>{daily_gens}</b>
• За последний час: <b>{hourly_gens}</b>

📈 <b>Активность за 24ч</b>
{sparkline(hourly_counts)}
Мин: {min(hourly_counts)} | Макс: {max(hourly_counts)} | Средн: {sum(hourly_counts) / len(hourly_counts):.1f}

💭 <b>Токены</b>
• Всего: <b>{total_tokens:,}</b>
• За 24ч: <b>{tokens_last_24h:,}</b>
• Сегодня: <b>{tokens_today:,}</b>
• За последний час: <b>{tokens_last_hour:,}</b>

💰 <b>Оценка затрат</b>
• Всего: <b>${all_time_costs['total']:.2f}</b>
• За 30 дней: <b>${last_30d_costs['total']:.2f}</b>"""

        # Add per-model breakdown
        response += "\n\n📊 <b>Использование моделей (30 дн)</b>"
        count = 0
        for usage in model_usage:
            if count >= 3:
                break
            model = usage['model']
            cost = costs['per_model'].get(model, 0)
            response += f"\n• {model}:"
            response += f" {usage['requests']} запр.,"
            response += f" {usage['total_tokens']:,} всего"
            if cost > 0:
                response += f" (${cost:.2f})"
            count += 1

        response += "\n\n💬 <b>Топ 5 чатов по использованию:</b>"
        for chat_stats in top_chats_costs:
            chat_title = await get_entity_title(chat_stats['id'])
            chat_costs = await stats.calculate_costs([{
                'model': m,
                'context_tokens': d['context_tokens'],
                'completion_tokens': d['completion_tokens']
            } for m, d in chat_stats['models'].items()])
            response += f"\n• {chat_title} (<code>{chat_stats['id']}</code>): "
            response += f"<b>{chat_stats['total_tokens']:,}</b> токенов, "
            response += f"{chat_stats['total_requests']} запросов"
            response += f" (${chat_costs['total']:.2f})"

        response += "\n\n👤 <b>Самые активные пользователи:</b>"
        for user_stats in top_users_costs:
            user_name = await get_entity_title(user_stats['id'])
            user_costs = await stats.calculate_costs([{
                'model': m,
                'context_tokens': d['context_tokens'],
                'completion_tokens': d['completion_tokens']
            } for m, d in user_stats['models'].items()])
            response += f"\n• {user_name} (<code>{user_stats['id']}</code>): "
            response += f"<b>{user_stats['total_tokens']:,}</b> токенов, "
            response += f"{user_stats['total_requests']} запросов"
            response += f" (${user_costs['total']:.2f})"

        response_time = time.time() - start_time
        response += f"\n\n⚡️ Сгенерировано за {response_time:.2f}с"

        await message.reply(response)

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        logger.debug(traceback.format_exc())
        await message.reply("❌ Не удалось сгенерировать статистику")
