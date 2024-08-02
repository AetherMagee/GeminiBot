import os
from typing import Optional

from aiogram.types import Message
from loguru import logger

import api.google
import db
from utils import log_command

GIT_COMMIT_HASH: Optional[str] = None


def get_git_commit_hash() -> str:
    global GIT_COMMIT_HASH
    if GIT_COMMIT_HASH is None:
        try:
            git_head_path = os.path.join('.git', 'HEAD')
            if os.path.exists(git_head_path):
                with open(git_head_path, 'r') as f:
                    content = f.read().strip()
                if content.startswith('ref: '):
                    ref_path = os.path.join('.git', content[5:])
                    if os.path.exists(ref_path):
                        with open(ref_path, 'r') as f:
                            GIT_COMMIT_HASH = f.read().strip()[:7]  # Short hash
                else:
                    GIT_COMMIT_HASH = content[:7]  # Short hash for detached HEAD
            if not GIT_COMMIT_HASH:
                raise FileNotFoundError
        except Exception as e:
            logger.error(f"Error reading git commit hash: {e}")
            GIT_COMMIT_HASH = "Unknown"
    return GIT_COMMIT_HASH


async def status_command(message: Message):
    log_command(message)
    messages = await db.get_messages(message.chat.id)

    messages_limit = await db.get_chat_parameter(message.chat.id, "message_limit")
    current_model = await db.get_chat_parameter(message.chat.id, "model")
    commit = get_git_commit_hash()

    text_to_send = f"""✅ <b>Бот активен!</b>
💬 <b>Память:</b> {len(messages)}/{messages_limit} сообщений <i>(⏱ Секунду...)</i>
✨ <b>Модель:</b> <i>{current_model}</i>
🆔 <b>ID чата:</b> <code>{message.chat.id}</code>
🤓 <b>Версия бота:</b> <code>{commit}</code>"""

    reply = await message.reply(text_to_send)

    token_count = await api.google.count_tokens_for_chat(messages,
                                                         await db.get_chat_parameter(message.chat.id, "model"))
    text_to_send = text_to_send.replace("⏱ Секунду...", f"{token_count} токенов")
    await reply.edit_text(text_to_send)
