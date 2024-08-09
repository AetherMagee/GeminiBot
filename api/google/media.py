import asyncio
import base64
import os
import sys
import threading
from io import BytesIO
from typing import Union

import google.generativeai as genai
from aiogram.types import Message, Sticker, VideoNote
from google.generativeai.types import File
from loguru import logger
from PIL import Image

from main import bot


class ReturnValueThread(threading.Thread):
    def __init__(self, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None
        self.target = target

    def run(self):
        if not self.target:
            return
        try:
            self.result = self.target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)


async def _download_if_necessary(file_id: str):
    if not os.path.exists(f"/cache/{file_id}"):
        logger.debug(f"Downloading {file_id}")
        await bot.download(file_id, f"/cache/{file_id}")


async def get_other_media(message: Message, gemini_token: str) -> list:
    uploaded_media = []

    for media_type in [message.audio, message.video, message.voice, message.document, message.video_note, message.sticker]:
        if media_type and media_type.file_size < 10_000_000:
            logger.debug(f"Downloading {type(media_type)} | {media_type.file_id}")
            await _download_if_necessary(media_type.file_id)
            try:
                mime_type = media_type.mime_type
            except AttributeError:
                if isinstance(media_type, VideoNote):
                    mime_type = "video/mp4"
                elif isinstance(media_type, Sticker):
                    if media_type.is_video:
                        mime_type = "video/mp4"
                    else:
                        mime_type = "image/webp"
                else:
                    continue
            logger.debug(f"Uploading {media_type.file_id} on token {gemini_token}")

            genai.configure(api_key=gemini_token)
            upload_thread = ReturnValueThread(target=genai.upload_file, kwargs={
                "path": "/cache/" + media_type.file_id,
                "display_name": f"Media file by {message.from_user.id}",
                "mime_type": mime_type
            })
            upload_thread.start()
            while upload_thread.is_alive():
                await asyncio.sleep(0.25)
            upload_result: File = upload_thread.result

            waited = 0
            while upload_result.state == "PROCESSING" and waited < 12:  # Wait for a max of 3 seconds
                await asyncio.sleep(0.25)
                waited += 1

            uploaded_media.append(upload_result)

    if message.reply_to_message:
        uploaded_media = uploaded_media + await get_other_media(message.reply_to_message, gemini_token)

    return uploaded_media


async def get_photo(message: Message, mode: str = "pillow") -> Union[Image, bytes]:
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo[-1].file_id
    else:
        photo_file_id = None

    if photo_file_id:
        if mode == "pillow":
            await _download_if_necessary(photo_file_id)
            return Image.open(f"/cache/{photo_file_id}")
        elif mode == "base64":
            downloaded_bytes: BytesIO = await bot.download(photo_file_id)
            return base64.b64encode(downloaded_bytes.getvalue()).decode("utf-8")
