import api.google
import api.openai


chat_configs = {
    "all_endpoints": {
        "endpoint": {
            "description": "Какая система используется ботом для генерации ответов",
            "type": "text",
            "default_value": "\'google\'",
            "accepted_values": ["google", "openai"],
            "protected": True  # Only the bot's admin can change this
        },
        "message_limit": {
            "description": "Максимум сообщений в памяти бота",
            "type": "integer",
            "default_value": 500,
            "accepted_values": range(1, 3000),
            "protected": False
        },
        "memory_alter_permission": {
            "description": "Кто может пользоваться командами /reset и /forget",
            "type": "text",
            "default_value": "\'all\'",
            "accepted_values": ["all", "admins", "owner"],
            "protected": False
        },
        "show_error_messages": {
            "description": "Показывать ли подробные сообщения об ошибке",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False
        },
    },
    "google": {
        "g_model": {
            "description": "Используемая ботом модель Gemini",
            "type": "text",
            "default_value": "\'gemini-1.5-pro-latest\'",
            "accepted_values": api.google.get_available_models(),
            "protected": False
        }
    },
    "openai": {
        "o_model": {
            "description": "Используемая ботом модель",
            "type": "text",
            "default_value": "\'gpt-4o\'",
            "accepted_values": api.openai.get_available_models(),
            "protected": False
        },
        "o_auto_fallback": {
            "description": "Разрешить ли боту автоматически переключаться на Gemini API в случае сбоя эндпоинта OpenAI",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False
        }
    }
}
