import asyncio
import traceback
from datetime import datetime, timedelta
from typing import List

from aiogram.types import Message
from loguru import logger

import db.statistics as stats
from utils import get_entity_title, log_command


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
    await log_command(message)

    try:
        now = datetime.now()
        start_of_today = datetime.combine(now.date(), datetime.min.time())
        one_hour_ago = now - timedelta(hours=1)

        # Active users
        active_users = await asyncio.gather(
            stats.get_active_users(1),
            stats.get_active_users(7),
            stats.get_active_users(30)
        )
        daily_active_count, _ = active_users[0]
        weekly_active_count, _ = active_users[1]
        monthly_active_count, _ = active_users[2]

        # Generation counts
        generation_counts = await asyncio.gather(
            stats.get_generation_counts_period(start_of_today),
            stats.get_generation_counts_period(one_hour_ago),
            stats.get_generation_counts(7),
            stats.get_generation_counts_period(datetime.min)
        )
        daily_gens, hourly_gens, weekly_gens, total_gens = generation_counts

        # Token stats
        token_stats = await asyncio.gather(
            stats.get_token_stats(),
            stats.get_tokens_consumed(1),
            stats.get_tokens_consumed_period(start_of_today),
            stats.get_tokens_consumed_period(one_hour_ago)
        )
        (total_tokens, top_chats) = token_stats[0]
        tokens_last_24h = token_stats[1]
        tokens_today = token_stats[2]
        tokens_last_hour = token_stats[3]

        # Enhanced stats
        enhanced_stats = await asyncio.gather(
            stats.get_hourly_stats(24),
            stats.get_model_usage(30),
            stats.get_total_cost_stats(),
            stats.get_cost_stats_for_entities('chat', 3),
            stats.get_cost_stats_for_entities('user', 3),
            stats.get_cache_stats()
        )
        hourly_counts = enhanced_stats[0]
        model_usage = enhanced_stats[1]
        total_stats = enhanced_stats[2]
        top_chats_costs = enhanced_stats[3]
        top_users_costs = enhanced_stats[4]
        cache_stats = enhanced_stats[5]

        # Calculate costs
        costs = await stats.calculate_costs(model_usage)
        all_time_costs = await stats.calculate_costs(total_stats['all_time'])
        last_30d_costs = await stats.calculate_costs(total_stats['last_30d'])

        async def format_entity_stats(entities, entity_type=""):
            formatted = f"\n\n{'💬' if entity_type == 'chat' else '👤'} <b>{'Топ чатов' if entity_type == 'chat' else 'Самые активные пользователи'}:</b>"

            # Get all titles concurrently
            entity_titles = await asyncio.gather(
                *[get_entity_title(entity['id']) for entity in entities]
            )

            # Zip entities with their titles and format
            for entity, title in zip(entities, entity_titles):
                entity_costs = await stats.calculate_costs([{
                    'model': m,
                    'context_tokens': d['context_tokens'],
                    'completion_tokens': d['completion_tokens']
                } for m, d in entity['models'].items()])

                formatted += f"\n• {title} (<code>{entity['id']}</code>): "
                formatted += f"<b>{entity['total_requests']}</b> запросов, "
                formatted += f"<b>{entity['total_tokens']:,}</b> токенов"
                formatted += f" (${entity_costs['total']:.2f})"

            return formatted

        # Format model usage
        model_usage_text = "\n\n📊 <b>Использование моделей (30 дн)</b>"
        for usage in model_usage[:3]:
            model = usage['model']
            cost = costs['per_model'].get(model, 0)
            model_usage_text += (f"\n• {model}: {usage['requests']} запросов, "
                                 f"{usage['total_tokens']:,} токенов"
                                 f"{f' (${cost:.2f})' if cost > 0 else ''}")

        # Build base response
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

        # Add model usage
        response += model_usage_text

        # Add entity stats
        entity_stats = await asyncio.gather(
            format_entity_stats(top_chats_costs, "chat"),
            format_entity_stats(top_users_costs, "user")
        )
        response += entity_stats[0] + entity_stats[1]

        response += "\n\n💾 <b>Кэши:</b>"
        for cache_name, info in cache_stats.items():
            response += f"\n• {cache_name}: {info['size']}/{info['maxsize']}"
            response += f" - {info['hit_rate']}% попаданий ({info['hits']:,} к {info['misses']:,})"

        db_stats = await stats.get_database_stats()

        response += "\n\n💾 <b>База данных:</b>"
        response += f"\n• Размер: {db_stats['total_size']}"
        response += f"\n• Попадания по кэшам: {db_stats['cache_hit_ratio']:.1%}"

        conn_stats = db_stats["connections"]
        response += f"\n• Подключения: {conn_stats['total']} всего "
        response += f"({conn_stats['active']} активных, {conn_stats['idle']} простаивают)"

        response += "\n• Топ таблиц по размеру:"
        for table in list(db_stats["tables"])[:3]:
            response += f"\n  - {table['table_name']}: {table['total_size']} "
            response += f"({table['row_count']:,} строк)"

        await message.reply(response)

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        logger.debug(traceback.format_exc())
        await message.reply("❌ Не удалось собрать статистику")
