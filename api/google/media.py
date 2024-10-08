import asyncio
import base64
import os
import traceback
from typing import Dict, List, Union

import aiohttp
import puremagic
from aiogram.types import Message
from asyncpg import Record
from loguru import logger
from PIL import Image

import db
from main import bot
from ..media import get_file_id_from_chain

cache_path = os.getenv('CACHE_PATH')


async def _download_if_necessary(file_id: str):
    if not os.path.exists(cache_path + file_id):
        logger.info(f"Downloading {file_id}")
        await bot.download(file_id, cache_path + file_id)


async def get_other_media(message: Message, gemini_token: str, all_messages: List[Record]) -> Dict[str, str]:
    file_id = await get_file_id_from_chain(
        message.message_id,
        all_messages,
        "other",
        int(await db.get_chat_parameter(message.chat.id, "media_context_max_depth"))
    )

    if file_id:
        await _download_if_necessary(file_id)

        mime_type = puremagic.from_file(cache_path + file_id, mime=True)
        if mime_type == "application/octet-stream":
            mime_type = "application/pdf"

        logger.info(f"Uploading {file_id} of type {mime_type} on token {gemini_token}")

        # Set up headers and data for the resumable upload request
        session_headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(os.path.getsize("/cache/" + file_id)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json"
        }

        data = {
            "file": {
                "display_name": file_id
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={gemini_token}",
                    headers=session_headers,
                    json=data
            ) as response:
                upload_headers = response.headers
                upload_url = upload_headers.get("X-Goog-Upload-URL")

            if upload_url:
                async with session.post(
                        upload_url,
                        headers={
                            "Content-Length": str(os.path.getsize(cache_path + file_id)),
                            "X-Goog-Upload-Offset": "0",
                            "X-Goog-Upload-Command": "upload, finalize"
                        },
                        data=open(cache_path + file_id, "rb")
                ) as response:
                    upload_result = await response.json()

                logger.info("Waiting for the file to become available...")
                sleep_time = 0.25
                total_sleep_time = 0
                max_sleep_time = 5
                while total_sleep_time < max_sleep_time:
                    await asyncio.sleep(sleep_time)
                    async with session.get(upload_result['file']['uri'] + f"?key={gemini_token}") as response:
                        decoded_response = await response.json()
                        if decoded_response['state'] == "ACTIVE":
                            break
                    total_sleep_time += sleep_time

                if total_sleep_time > 1:
                    logger.warning(f"Waited for {total_sleep_time}s for the file to process")

                return {
                    "mime_type": mime_type,
                    "uri": upload_result['file']['uri'],
                }


async def get_photo(message: Message, all_messages: List[Record], mode: str = "pillow") -> Union[Image, bytes]:
    photo_file_id = await get_file_id_from_chain(
        message.message_id,
        all_messages,
        "photo",
        int(await db.get_chat_parameter(message.chat.id, "media_context_max_depth"))
    )

    if photo_file_id:
        logger.debug(f"Loading an image with mode {mode}")
        await _download_if_necessary(photo_file_id)
        if mode == "pillow":
            return Image.open(cache_path + photo_file_id)
        elif mode == "base64":
            with open(cache_path + photo_file_id, "rb") as f:
                try:
                    result = base64.b64encode(f.read()).decode("utf-8")
                except Exception as exc:
                    traceback.print_exc()
            return result
