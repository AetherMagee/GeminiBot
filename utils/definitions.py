import os

import api.google
import api.openai
from .frange import frange

chat_configs = {
    "all_endpoints": {
        "endpoint": {
            "description": "Какая система используется ботом для генерации ответов",
            "type": "text",
            "default_value": "\'google\'",
            "accepted_values": ["google", "openai"] if os.getenv("OAI_ENABLED").lower() == "true" else ["google"],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "message_limit": {
            "description": "Максимум сообщений в памяти бота",
            "type": "integer",
            "default_value": 250,
            "accepted_values": range(1, 5000),
            "protected": False,
            "advanced": False,
            "private": False
        },
        "memory_alter_permission": {
            "description": "Кто может пользоваться командами /reset и /forget",
            "type": "text",
            "default_value": "\'all\'",
            "accepted_values": ["all", "admins", "owner"],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "show_advanced_settings": {
            "description": "Показ продвинутых настроек в /settings (они всё еще доступны в /set)",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "show_error_messages": {
            "description": "Показывать ли подробные сообщения об ошибке",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
            "private": False
        },
        "add_reply_to": {
            "description": "Добавлять ли в сообщения \"REPLY TO\", чтобы показать модели, кто кому отвечает",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
            "private": False
        },
        "token_limit": {
            "description": "Желаемое максимальное количество токенов в памяти бота. <code>0</code> - отключает лимит",
            "type": "integer",
            "default_value": 0,
            "accepted_values": range(0, 127990),
            "protected": False,
            "advanced": False,
            "private": False
        },
        "token_limit_action": {
            "description": "Что делать при достижении лимита токенов",
            "type": "text",
            "default_value": "\'warn\'",
            "accepted_values": ["warn", "block"],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "max_output_tokens": {
            "description": "Максимальная длина ответа, что может сгенерировать бот",
            "type": "integer",
            "default_value": 2048,
            "accepted_values": range(0, 65536),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "media_context_max_depth": {
            "description": "Сколько сообщений сканировать на наличие медиафайлов в цепочке ответов",
            "type": "integer",
            "default_value": 5,
            "accepted_values": range(1, 20),
            "protected": False,
            "advanced": True,
            "private": False
        }
    },
    "google": {
        "g_model": {
            "description": "Используемая ботом модель Gemini",
            "type": "text",
            "default_value": "\'gemini-1.5-pro-latest\'",
            "accepted_values": api.google.get_available_models(),
            "protected": False,
            "advanced": False,
            "private": False
        },
        "g_safety_threshold": {
            "description": "На каком уровне уверенности в небезопасности контента блокировать ответ бота.\nP.S. Даже "
                           "при block_none всё равно происходит сканирование на наличие CSAM и подобного.",
            "type": "text",
            "default_value": "\'none\'",
            "accepted_values": ["none", "only_high", "medium_and_above", "low_and_above"],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "g_temperature": {
            "description": "Температура сэмплинга. Чем выше - тем более случайные ответы может вернуть модель",
            "type": "decimal",
            "default_value": 1.0,
            "accepted_values": frange(0, 2, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "g_top_p": {
            "description": "Вероятностный порог для nucleus sampling. Модель рассматривает только токены, "
                           "чья суммарная вероятность не превышает этот порог",
            "type": "decimal",
            "default_value": 0.95,
            "accepted_values": frange(0, 1, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "g_top_k": {
            "description": "Количество наиболее вероятных токенов, из которых модель выбирает при генерации. Меньшие "
                           "значения делают вывод более предсказуемым",
            "type": "integer",
            "default_value": 40,
            "accepted_values": range(1, 100),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "g_code_execution": {
            "description": "Разрешить ли модели выполнять код Python в выделенном контейнере. Применяются <a "
                           "href=\"https://ai.google.dev/gemini-api/docs/code-execution?lang=python#limitations"
                           "\">ограничения</a>.",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False,
            "private": False
        },
    },
    "openai": {
        "o_url": {
            "description": "Ссылка на эндпоинт, который будет использовать бот.",
            "type": "text",
            "default_value": None,
            "accepted_values": None,
            "protected": False,
            "advanced": False,
            "private": True
        },
        "o_key": {
            "description": "Ключ авторизации для эндпоинта, установленного в <code>o_url</code>",
            "type": "text",
            "default_value": None,
            "accepted_values": None,
            "protected": False,
            "advanced": False,
            "private": True
        },
        "o_model": {
            "description": "Используемая ботом модель",
            "type": "text",
            "default_value": "\'gpt-4o\'",
            "accepted_values": None,
            "protected": False,
            "advanced": False,
            "private": False
        },
        "o_auto_fallback": {
            "description": "Разрешить ли боту автоматически переключаться на Gemini API в случае сбоя эндпоинта OpenAI",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "o_add_system_prompt": {
            "description": "Добавлять ли встроенное системное сообщение, нацеленное на улучшение качества ответов",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_vision": {
            "description": "Разрешить ли модели работать с изображениями",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "o_timeout": {
            "description": "Максимальное время ожидания ответа OpenAI API",
            "type": "integer",
            "default_value": 60,
            "accepted_values": range(1, 300),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_temperature": {
            "description": "Температура сэмплинга. Чем выше - тем более случайные ответы может вернуть модель",
            "type": "decimal",
            "default_value": 1.0,
            "accepted_values": frange(0, 2, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_top_p": {
            "description": "Вероятностный порог для nucleus sampling. Модель рассматривает только токены, "
                           "чья суммарная вероятность не превышает этот порог",
            "type": "decimal",
            "default_value": 1.0,
            "accepted_values": frange(0, 1, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_presence_penalty": {
            "description": "Штраф за повторение тем. Положительные значения поощряют модель говорить о новых темах",
            "type": "decimal",
            "default_value": 0.0,
            "accepted_values": frange(-2, 2, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_frequency_penalty": {
            "description": "Штраф за повторение конкретных слов. Положительные значения снижают вероятность "
                           "повторения одних и тех же фраз",
            "type": "decimal",
            "default_value": 0.0,
            "accepted_values": frange(-2, 2, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_log_prompt": {
            "description": "Сохранять ли запросы в логи бота. Полезно при отладке администраторами.",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": True,
            "advanced": True,
            "private": False
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
