chat_configs = {
    "message_limit": {
        "description": "Максимум сообщений в памяти бота",
        "type": "integer",
        "default_value": 500,
        "accepted_values": range(1, 3000)
    },
    "reset_permission": {
        "description": "Кто может пользоваться командой /reset",
        "type": "text",
        "default_value": "\'all\'",
        "accepted_values": ["all", "admins", "owner"]
    },
    "show_error_messages": {
        "description": "Показывать ли подробные сообщения об ошибке",
        "type": "boolean",
        "default_value": False,
        "accepted_values": [True, False]
    }
}
