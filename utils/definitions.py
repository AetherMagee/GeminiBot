from .frange import frange
import api.google
import api.openai

chat_configs = {
    "all_endpoints": {
        "endpoint": {
            "description": "Какая система используется ботом для генерации ответов",
            "type": "text",
            "default_value": "\'google\'",
            "accepted_values": ["google", "openai"],
            "protected": True,  # Only the bot's admin can change this
            "advanced": False
        },
        "message_limit": {
            "description": "Максимум сообщений в памяти бота",
            "type": "integer",
            "default_value": 1000,
            "accepted_values": range(1, 5000),
            "protected": False,
            "advanced": False
        },
        "memory_alter_permission": {
            "description": "Кто может пользоваться командами /reset и /forget",
            "type": "text",
            "default_value": "\'all\'",
            "accepted_values": ["all", "admins", "owner"],
            "protected": False,
            "advanced": False
        },
        "show_advanced_settings": {
            "description": "Показ продвинутых настроек в /settings (они всё еще доступны в /set)",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False
        },
        "show_error_messages": {
            "description": "Показывать ли подробные сообщения об ошибке",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True
        },
        "add_reply_to": {
            "description": "Добавлять ли в сообщения \"REPLY TO\", чтобы показать модели, кто кому отвечает",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True
        },
        "token_limit": {
            "description": "Желаемое максимальное количество токенов в памяти бота. <code>0</code> - отключает лимит",
            "type": "integer",
            "default_value": 0,
            "accepted_values": range(0, 128000),
            "protected": False,
            "advanced": False
        },
        "token_limit_action": {
            "description": "Что делать при достижении лимита токенов",
            "type": "text",
            "default_value": "\'warn\'",
            "accepted_values": ["warn", "block"],
            "protected": False,
            "advanced": False
        },
        "max_output_tokens": {
            "description": "Максимальная длина ответа, что может сгенерировать бот",
            "type": "integer",
            "default_value": 2048,
            "accepted_values": range(0, 8192),
            "protected": False,
            "advanced": True
        },
        "media_context_max_depth": {
            "description": "Сколько сообщений сканировать на наличие медиафайлов в цепочке ответов",
            "type": "integer",
            "default_value": 5,
            "accepted_values": range(1, 20),
            "protected": False,
            "advanced": True
        }
    },
    "google": {
        "g_model": {
            "description": "Используемая ботом модель Gemini",
            "type": "text",
            "default_value": "\'gemini-1.5-pro-latest\'",
            "accepted_values": api.google.get_available_models(),
            "protected": False,
            "advanced": False
        },
        "g_temperature": {
            "description": "Температура сэмплинга. Чем выше - тем более случайные ответы может вернуть модель",
            "type": "decimal",
            "default_value": 1.0,
            "accepted_values": frange(0, 1, 0.01),
            "protected": False,
            "advanced": True
        },
        "g_top_p": {
            "description": "Вероятностный порог для nucleus sampling. Модель рассматривает только токены, "
                           "чья суммарная вероятность не превышает этот порог",
            "type": "decimal",
            "default_value": 0.95,
            "accepted_values": frange(0, 1, 0.01),
            "protected": False,
            "advanced": True
        },
        "g_top_k": {
            "description": "Количество наиболее вероятных токенов, из которых модель выбирает при генерации. Меньшие "
                           "значения делают вывод более предсказуемым",
            "type": "integer",
            "default_value": 40,
            "accepted_values": range(1, 100),
            "protected": False,
            "advanced": True
        }
    },
    "openai": {
        "o_model": {
            "description": "Используемая ботом модель",
            "type": "text",
            "default_value": "\'gpt-4o\'",
            "accepted_values": api.openai.get_hardcoded_models() if not api.openai.get_available_models() else api.openai.get_available_models(),
            "protected": False,
            "advanced": False
        },
        "o_auto_fallback": {
            "description": "Разрешить ли боту автоматически переключаться на Gemini API в случае сбоя эндпоинта OpenAI",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False
        },
        "o_add_system_prompt": {
            "description": "Добавлять ли системное сообщение, нацеленное на улучшение качества ответов",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
        },
        "o_vision": {
            "description": "Разрешить ли модели работать с изображениями",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False
        },
        "o_timeout": {
            "description": "Максимальное время ожидания ответа OpenAI API",
            "type": "integer",
            "default_value": 60,
            "accepted_values": range(1, 120),
            "protected": False,
            "advanced": True
        },
        "o_temperature": {
            "description": "Температура сэмплинга. Чем выше - тем более случайные ответы может вернуть модель",
            "type": "decimal",
            "default_value": 1.0,
            "accepted_values": frange(0, 2, 0.01),
            "protected": False,
            "advanced": True
        },
        "o_top_p": {
            "description": "Вероятностный порог для nucleus sampling. Модель рассматривает только токены, "
                           "чья суммарная вероятность не превышает этот порог",
            "type": "decimal",
            "default_value": 1.0,
            "accepted_values": frange(0, 1, 0.01),
            "protected": False,
            "advanced": True
        },
        "o_presence_penalty": {
            "description": "Штраф за повторение тем. Положительные значения поощряют модель говорить о новых темах",
            "type": "decimal",
            "default_value": 0.0,
            "accepted_values": frange(-2, 2, 0.01),
            "protected": False,
            "advanced": True
        },
        "o_frequency_penalty": {
            "description": "Штраф за повторение конкретных слов. Положительные значения снижают вероятность "
                           "повторения одних и тех же фраз",
            "type": "decimal",
            "default_value": 0.0,
            "accepted_values": frange(-2, 2, 0.01),
            "protected": False,
            "advanced": True
        },
        "o_clarify_target_message": {
            "description": "Добавлять ли дополнительные инструкции, помогающие модели понять, на что конкретно нужно "
                           "отвечать",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True
        },
        "o_log_prompt": {
            "description": "кирилл если будешь это дергать я тебя выебу",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": True,
            "advanced": True
        }
    }
}

presets = {
    "default": {
        "max_output_tokens": 2048,
        "o_model": "gpt-4o",
        "g_model": "gemini-1.5-pro-latest",
        "o_add_system_prompt": True,
        "o_clarify_target_message": True,
        "o_timeout": 60,
        "o_vision": True
    },
    "o1": {
        "endpoint": "openai",
        "max_output_tokens": 32768,
        "o_model": "o1-preview",
        "o_vision": False,
        "o_timeout": 300,
        "o_add_system_prompt": False,
        "o_clarify_target_message": False
    }
}