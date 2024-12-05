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
            "default_value": 50,
            "accepted_values": range(1, 2500),
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
        "process_markdown": {
            "description": "Позволить ли Телеграму автоматически обрабатывать форматирование Markdown в ответах бота",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
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
            "description": "Добавлять ли в сообщения \"> \", чтобы показать модели, кто кому отвечает",
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
            "advanced": True,
            "private": False
        },
        "token_limit_action": {
            "description": "Что делать при достижении лимита токенов",
            "type": "text",
            "default_value": "\'warn\'",
            "accepted_values": ["warn", "block"],
            "protected": False,
            "advanced": True,
            "private": False
        },
        "max_output_tokens": {
            "description": "Максимальная длина ответа, что может сгенерировать бот",
            "type": "integer",
            "default_value": 1024,
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
        },
        "max_requests_per_hour": {
            "description": "Сколько запросов в час можно отправлять в бота. Устанавливается администраторами бота. Можно "
                           "запросить повышение лимита через команду обратной связи (просто так не повышаем)",
            "type": "integer",
            "default_value": 80,
            "accepted_values": range(0, 1200),
            "protected": True,
            "advanced": False,
            "private": False
        }
    },
    "google": {
        "g_model": {
            "description": "Используемая ботом модель Gemini",
            "type": "text",
            "default_value": "\'gemini-1.5-pro-latest\'",
            "accepted_values": api.google.get_available_models,
            "protected": False,
            "advanced": False,
            "private": False
        },
        "g_safety_threshold": {
            "description": "На каком уровне уверенности в небезопасности контента блокировать ответ бота.\nP.S. Даже "
                           "при уровне <code>none</code> всё равно происходит сканирование на наличие CSAM и подобного.",
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
        "g_web_search": {
            "description": "Разрешить ли Gemini API использовать веб-поиск, также известный как <a "
                           "href=\"https://ai.google.dev/gemini-api/docs/grounding\">Grounding</a>",
            "type": "boolean",
            "default_value": False,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": False,
            "private": False
        },
        "g_web_threshold": {
            "description": "Коэффициент требовательности к подтверждению моделей её слов. Грубо говоря, чем выше "
                           "значение, тем больше модель будет проверять себя с помощью веб-поиска",
            "type": "decimal",
            "default_value": 0.73,
            "accepted_values": frange(0, 1.0, 0.01),
            "protected": False,
            "advanced": True,
            "private": False
        },
        "g_web_show_queries": {
            "description": "Добавлять ли в конец сообщения запросы, которые отправлял Gemini API в Google для "
                           "генерации ответа",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
            "private": False
        },
        "g_web_show_sources": {
            "description": "Добавлять ли в конец сообщения источники, которыми воспользовался Gemini API для "
                           "генерации ответа",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
            "private": False
        }
    },
    "openai": {
        "o_url": {
            "description": "Ссылка на эндпоинт, который будет использовать бот. \nБЕЗ /v1/chat/completions\nЕсли не установлено, используется стандартный эндпоинт",
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
            "accepted_values": api.openai.get_available_models,
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
        "o_add_system_messages": {
            "description": "Добавлять ли любые системные сообщения в контекст. При отключении скрывает и встроенный системный промпт, и сообщения, добавленные через /system",
            "type": "boolean",
            "default_value": True,
            "accepted_values": [True, False],
            "protected": False,
            "advanced": True,
            "private": False
        },
        "o_clarify_target_message": {
            "description": "Добавлять ли дополнительное системное сообщение, чтобы помочь модели понять, на что нужно "
                           "отвечать",
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
        "max_output_tokens": 1024,
        "o_model": "gpt-4o",
        "g_model": "gemini-1.5-pro-latest",
        "o_add_system_prompt": True,
        "o_add_system_messages": True,
        "o_timeout": 60,
        "o_vision": True,
        "o_clarify_target_message": True
    },
    "o1": {
        "endpoint": "openai",
        "max_output_tokens": 32768,
        "o_model": "o1-preview",
        "o_vision": False,
        "o_timeout": 300,
        "o_add_system_messages": False,
        "o_clarify_target_message": False
    }
}

prices = {
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00
    },
    "gpt-4o-2024-11-20": {
        "input": 2.50,
        "output": 10.00
    },
    "gpt-4o-2024-08-06": {
        "input": 2.50,
        "output": 10.00
    },
    "gpt-4o-2024-05-13": {
        "input": 5.00,
        "output": 15.00
    },
    "gpt-4o-audio-preview": {
        "text_input": 2.50,
        "text_output": 10.00,
        "audio_input": 100.00,
        "audio_output": 200.00
    },
    "gpt-4o-audio-preview-2024-10-01": {
        "text_input": 2.50,
        "text_output": 10.00,
        "audio_input": 100.00,
        "audio_output": 200.00
    },

    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60
    },
    "gpt-4o-mini-2024-07-18": {
        "input": 0.15,
        "output": 0.60
    },

    "o1-preview": {
        "input": 15.00,
        "output": 60.00
    },
    "o1-preview-2024-09-12": {
        "input": 15.00,
        "output": 60.00
    },

    "o1-mini": {
        "input": 3.00,
        "output": 12.00
    },
    "o1-mini-2024-09-12": {
        "input": 3.00,
        "output": 12.00
    },

    "chatgpt-4o-latest": {
        "input": 5.00,
        "output": 15.00
    },
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00
    },
    "gpt-4-turbo-2024-04-09": {
        "input": 10.00,
        "output": 30.00
    },
    "gpt-4": {
        "input": 30.00,
        "output": 60.00
    },
    "gpt-4-32k": {
        "input": 60.00,
        "output": 120.00
    },
    "gpt-4-0125-preview": {
        "input": 10.00,
        "output": 30.00
    },
    "gpt-4-1106-preview": {
        "input": 10.00,
        "output": 30.00
    },
    "gpt-4-vision-preview": {
        "input": 10.00,
        "output": 30.00
    },

    "gpt-3.5-turbo-0125": {
        "input": 0.50,
        "output": 1.50
    },
    "gpt-3.5-turbo-instruct": {
        "input": 1.50,
        "output": 2.00
    },
    "gpt-3.5-turbo-1106": {
        "input": 1.00,
        "output": 2.00
    },
    "gpt-3.5-turbo-0613": {
        "input": 1.50,
        "output": 2.00
    },
    "gpt-3.5-turbo-16k-0613": {
        "input": 3.00,
        "output": 4.00
    },
    "gpt-3.5-turbo-0301": {
        "input": 1.50,
        "output": 2.00
    },

    # Anthropic Claude models
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.00,
        "output": 15.00
    },
    "claude-3-5-haiku-20241022": {
        "input": 1.00,
        "output": 5.00
    },
    "claude-3-sonnet-20240229": {
        "input": 3.00,
        "output": 15.00
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25
    },

    # Google models
    "gemini-1.5-pro-latest": {
        "input": 2.50,
        "output": 10.00
    },
    "gemini-1.5-pro": {
        "input": 2.50,
        "output": 10.00
    },
    "gemini-pro": {
        "input": 2.50,
        "output": 10.00
    },
    "gemini-1.0-pro": {
        "input": 2.50,
        "output": 10.00
    },
}