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
}
