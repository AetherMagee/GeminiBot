import asyncio
import os
import random
from typing import List, Union

import google.generativeai as genai
from aiogram.types import Message
from asyncpg import Record
from google.api_core.exceptions import InvalidArgument
from google.generativeai import GenerationConfig
from google.generativeai.types import AsyncGenerateContentResponse, File, HarmBlockThreshold, HarmCategory
from loguru import logger

import db
from utils import get_message_text, simulate_typing
from .media import get_other_media, get_photo

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])

if not os.path.exists(os.getenv("GEMINI_API_KEYS_FILE_PATH")):
    logger.exception("No Gemini API keys file found")
    exit(1)

api_keys = []
with open(os.getenv("GEMINI_API_KEYS_FILE_PATH"), "r") as f:
    characters_to_remove = [" ", "\n"]
    for line in f.readlines():
        if line.startswith("AIza"):
            for character in characters_to_remove:
                line = line.replace(character, "")
            api_keys.append(line.strip())
random.shuffle(api_keys)
logger.info(f"Loaded {len(api_keys)} API keys")

api_key_index = 0
api_keys_error_counts = {}
with open(os.getenv("SYSTEM_PROMPT_FILE_PATH"), "r") as f:
    default_prompt = f.read()
MAX_API_ATTEMPTS = 3
ERROR_MESSAGES = {
    "unsupported_file_type": "❌ *Данный тип файлов не поддерживается Gemini API.*",
    "censored": "❌ *Запрос был заблокирован цензурой Gemini API.*",
    "unknown": "❌ *Произошёл сбой Gemini API{0}*",
    "system_failure": "Your response was supposed to be here, but you failed to reply for some reason. Be better next "
                      "time."
}


def _get_api_key() -> str:
    global api_key_index
    api_key_index += 1
    if api_key_index % 50 == 0:
        logger.debug(f"Error counts: {api_keys_error_counts}")
    return api_keys[api_key_index % len(api_keys)]


async def _call_gemini_api(request_id: int, prompt: list, token: str, model_name: str,
                           temperature: float, top_p: float, top_k: int, max_output_tokens: int) \
        -> Union[AsyncGenerateContentResponse, str, Exception, None]:
    safety = {
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
    }

    config = GenerationConfig(
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_output_tokens=max_output_tokens
    )

    logger.debug(f"{request_id} | Using model {model_name}")

    model = genai.GenerativeModel(model_name)

    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        if not any(isinstance(item, File) for item in prompt):
            token = _get_api_key()
            genai.configure(api_key=token)
            model = genai.GenerativeModel(model_name)
        else:
            logger.debug(f"{request_id} | Media in prompt, key rotation canceled")

        logger.info(f"{request_id} | Generating, attempt {attempt}/{MAX_API_ATTEMPTS}")
        try:
            response = await model.generate_content_async(
                prompt,
                safety_settings=safety,
                generation_config=config
            )
            return response
        except InvalidArgument:
            return ERROR_MESSAGES["unsupported_file_type"]
        except Exception as e:
            logger.error(f"{request_id} | Error \"{e}\" on key: {token}")
            if token not in api_keys_error_counts.keys():
                api_keys_error_counts[token] = 1
            else:
                api_keys_error_counts[token] += 1

            if attempt == MAX_API_ATTEMPTS:
                return e

    return None


async def format_message_for_prompt(message: Record, add_reply_to: bool = True) -> str:
    result = ""

    if message["sender_id"] == bot_id:
        result += "You: "
    else:
        if message["sender_username"] == message["sender_name"]:
            name = message["sender_name"]
        else:
            name = f"{message['sender_name']} ({message['sender_username']})"
        result += f"{name}: "

    if message["reply_to_message_id"] and add_reply_to:
        result += f"[REPLY TO: {message['reply_to_message_trimmed_text']}] "

    if message["text"]:
        result += message["text"]
    else:
        result += "*No text*"
    return result


async def _prepare_prompt(message: Message, chat_messages: List[Record], token: str) -> Union[list, None]:
    all_messages_list = [await format_message_for_prompt(msg) for msg in chat_messages]
    all_messages = "\n".join(all_messages_list)

    photos = [await get_photo(message, chat_messages)]
    photos = photos if photos[0] else []

    try:
        additional_media = await get_other_media(message, token, chat_messages)
    except AttributeError:
        return

    chat_type = "direct message (DM)" if message.from_user.id == message.chat.id else "group"
    chat_title = f" called {message.chat.title}" if message.from_user.id != message.chat.id else f" with {message.from_user.first_name}"

    media_warning = (
        "\n- Your target message or a message related to it happen to contain some media files. "
        "They have been attached for your analysis. When working with these files, follow these "
        "rules: 1) If you are sure that it wasn't described before in the chat history, "
        "describe PERFECTLY and AS THOROUGHLY AS POSSIBLE whatever is contained in the mediafile. "
        "You won't be able to see it again, and the User might ask additional questions, "
        "so these notes will also function as your future guidelines. When describing, start with "
        "\"This <media_type> contains\" in the User's language. For example, when working with an "
        "image and talking in a Russian -speaking chat, start with \"Это изображение содержит\". 2) "
        "Perform what the user asks you to do. So, if it's an image and the User wants the text on "
        "it - say it. If it's an audio resembling a voice message - transcript it as accurately as "
        "possible, then handle it as a normal message directed at you. So, if it has any "
        "instructions for you - execute them. Otherwise, ask the User what they want exactly."
    ) if photos or additional_media else ""

    prompt = default_prompt.format(
        chat_type=chat_type,
        chat_title=chat_title,
        all_messages=all_messages,
        target_message=all_messages_list[-1],
        media_warning=media_warning
    )

    return [prompt] + photos + additional_media


async def _handle_api_response(
        request_id: int,
        response: Union[AsyncGenerateContentResponse, str, Exception, None],
        message: Message,
        store: bool,
        show_error_message: bool
) -> str:
    if isinstance(response, AsyncGenerateContentResponse):
        logger.debug(f"{request_id} | {response.prompt_feedback} | {response.prompt_feedback.block_reason}")
        if response.prompt_feedback.block_reason:
            output = ERROR_MESSAGES["censored"]
            if random.randint(1, 4) == 3:
                output += ("\n\n_Если проблема повторяется - попробуйте /reset.\nЕсли есть идея, какое сообщение "
                           "вызывает блокировку - используйте на нем /forget_")
        else:
            output = response.text.replace("  ", " ")[:-1]
    elif isinstance(response, str):
        output = response
    elif isinstance(response, Exception):
        if show_error_message:
            if "have permission" in str(response):
                error_message = ": Бот перегружен файлами. Попробуйте снова через пару минут"
            elif "text is empty" in str(response):
                error_message = ": Был получен пустой ответ. Если проблема повторится, попробуйте /reset"
            elif "check quota" in str(response):
                error_message = ": Ежедневный ресурс API закончился"
            else:
                error_message = (": " + str(response))
        else:
            error_message = ""
        output = ERROR_MESSAGES["unknown"].format(error_message)
    else:
        logger.error(f"{request_id} | Unexpected response type: {type(response)}")
        if store:
            await db.save_system_message(message.chat.id, ERROR_MESSAGES["system_failure"])
        output = ERROR_MESSAGES['unknown'].format("")

    return output


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    token = _get_api_key()
    message_text = await get_message_text(message)

    logger.info(
        f"RID: {request_id} | UID: {message.from_user.id} | CID: {message.chat.id} | MID: {message.message_id}"
    )

    chat_messages = await db.get_messages(message.chat.id)
    typing_task = asyncio.create_task(simulate_typing(message.chat.id))

    if not message_text.startswith("/raw"):
        prompt = await _prepare_prompt(message, chat_messages, token)
        if not prompt:
            return ERROR_MESSAGES["censored"]

        store = True
    else:
        prompt = [message_text.replace("/raw ", "", 1)]
        store = "--dont-store" not in prompt[0]
        if not store:
            prompt[0] = prompt[0].replace("--dont-store", "", 1)

    model_name = await db.get_chat_parameter(message.chat.id, "model")

    api_task = asyncio.create_task(_call_gemini_api(
        request_id,
        prompt,
        token,
        model_name,
        float(await db.get_chat_parameter(message.chat.id, "g_temperature")),
        float(await db.get_chat_parameter(message.chat.id, "g_top_p")),
        int(await db.get_chat_parameter(message.chat.id, "g_top_k")),
        int(await db.get_chat_parameter(message.chat.id, "max_output_tokens"))
    ))

    response = await api_task
    typing_task.cancel()
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    logger.info(f"{request_id} | Complete")

    show_error_message = await db.get_chat_parameter(message.chat.id, "show_error_messages")

    try:
        return await _handle_api_response(request_id, response, message, store, show_error_message)
    except Exception as e:
        logger.error(f"{request_id} | Failed to generate message. Exception: {e}")
        if store:
            await db.save_system_message(message.chat.id, ERROR_MESSAGES['system_failure'])
        error_message = (": " + str(e)) if show_error_message else ""
        return ERROR_MESSAGES['unknown'].format(error_message)


async def count_tokens_for_chat(messages_list: list, model_name: str) -> int:
    key = _get_api_key()
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)

    all_messages_list = [await format_message_for_prompt(message) for message in messages_list]
    all_messages = "\n".join(all_messages_list)

    try:
        token_count = (await model.count_tokens_async(all_messages)).total_tokens
    except Exception as e:
        logger.error(f"Failed to count tokens. Exception: {e}")
        token_count = 0

    return token_count


def get_available_models() -> list:
    logger.info("GOOGLE | Getting available models...")
    genai.configure(api_key=_get_api_key())
    models = genai.list_models()
    model_list = []
    hidden = ["bison", "aqa", "embedding", "gecko"]
    for model in models:
        if not any(hidden_word in model.name for hidden_word in hidden):
            model_list.append(model.name.replace("models/", ""))

    return model_list
