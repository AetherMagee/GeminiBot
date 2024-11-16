import time
import traceback
from datetime import datetime, timedelta

from aiogram.types import Message
from loguru import logger

import db.statistics as stats
from main import ADMIN_IDS
from utils import sparkline


async def stats_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        start_time = time.time()

        # Define time periods
        now = datetime.now()
        periods = {
            'today': datetime.combine(now.date(), datetime.min.time()),
            'last_24h': now - timedelta(days=1),
            'last_hour': now - timedelta(hours=1),
            'last_30d': now - timedelta(days=30),
            'all_time': datetime.min
        }

        # Gather all statistics
        stats_data = {
            'costs': {
                'all_time': await stats.get_cost_analysis(periods['all_time']),
                'last_30d': await stats.get_cost_analysis(periods['last_30d'])
            },
            'hourly_activity': await stats.get_hourly_activity(24),
            'top_users': await stats.get_entity_stats('user', limit=5),
            'top_chats': await stats.get_entity_stats('chat', limit=5)
        }

        # Build response
        response = ["📊 <b>Статистика бота</b>\n", "💰 <b>Оценка затрат</b>",
                    f"• Всего: <b>${stats_data['costs']['all_time']['total_cost']:.2f}</b>",
                    f"• За 30 дней: <b>${stats_data['costs']['last_30d']['total_cost']:.2f}</b>",
                    "\n📈 <b>Активность за 24ч</b>", sparkline(stats_data['hourly_activity']),
                    f"Мин: {min(stats_data['hourly_activity'])} | "
                    f"Макс: {max(stats_data['hourly_activity'])} | "
                    f"Средн: {sum(stats_data['hourly_activity']) / len(stats_data['hourly_activity']):.1f}",
                    "\n📊 <b>Использование моделей (30 дн)</b>"]

        # Add model breakdown
        for model_stat in stats_data['costs']['last_30d']['model_usage']:
            model = model_stat['model']
            cost = stats_data['costs']['last_30d']['per_model'].get(model, 0)
            response.append(
                f"• {model}: {model_stat['requests']} запр., "
                f"{model_stat['total_tokens']:,} токенов"
                f" (${cost:.2f})"
            )

        # Add top entities
        response.append("\n💬 <b>Топ 5 чатов по использованию:</b>")
        for chat in stats_data['top_chats']:
            response.append(
                f"• {chat['name']} (<code>{chat['id']}</code>): "
                f"<b>{chat['total_tokens']:,}</b> токенов, "
                f"{chat['total_requests']} запросов"
                f" (${chat['total_cost']:.2f})"
            )

        response.append("\n👤 <b>Самые активные пользователи:</b>")
        for user in stats_data['top_users']:
            response.append(
                f"• {user['name']} (<code>{user['id']}</code>): "
                f"<b>{user['total_tokens']:,}</b> токенов, "
                f"{user['total_requests']} запросов"
                f" (${user['total_cost']:.2f})"
            )

        # Add generation time
        response_time = time.time() - start_time
        response.append(f"\n⚡️ Сгенерировано за {response_time:.2f}с")

        await message.reply("\n".join(response))

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        logger.debug(traceback.format_exc())
        await message.reply("❌ Не удалось сгенерировать статистику")