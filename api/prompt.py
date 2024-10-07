import os

from loguru import logger

default_sys_prompt_path = os.getenv("DATA_PATH") + "system_prompt.txt"
if not os.path.exists(default_sys_prompt_path):
    logger.exception(f"System prompt file not found. Please make sure that {default_sys_prompt_path} exists.")
    exit(1)
with open(default_sys_prompt_path, "r") as f:
    sys_prompt = f.read()


async def get_system_prompt() -> str:
    # TODO: Custom system prompts
    return sys_prompt
