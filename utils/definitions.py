chat_configs = {
    "message_limit": {
        "description": "Максимум сообщений в памяти бота",
        "type": "integer",
        "readable_type": "число",
        "default_value": 1000,
        "accepted_values": range(1, 5000)
    },
    "reset_permission": {
        "description": "Кто может пользоваться командой /reset",
        "type": "text",
        "readable_type": "текст",
        "default_value": "\'all\'",
        "accepted_values": ["all", "admins", "owner"]
    },
}
