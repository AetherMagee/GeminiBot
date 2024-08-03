import os

import google.generativeai as genai
from aiogram.types import Message, Sticker, VideoNote
from loguru import logger
from PIL import Image

from main import bot


async def _download_if_necessary(file_id: str):
    if not os.path.exists(f"/cache/{file_id}"):
        logger.debug(f"Downloading {file_id}")
        await bot.download(file_id, f"/cache/{file_id}")


async def get_other_media(message: Message, gemini_token: str) -> list:
    uploaded_media = []

    genai.configure(api_key=gemini_token)
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
            logger.debug(f"Uploading {media_type.file_id}")
            upload_result = genai.upload_file(path="/cache/" + media_type.file_id, display_name=f"Media file by {message.from_user.id}", mime_type=mime_type)
            uploaded_media.append(upload_result)

    if message.reply_to_message:
        uploaded_media = uploaded_media + await get_other_media(message.reply_to_message, gemini_token)

    return uploaded_media


async def get_photo(message: Message) -> Image:
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo[-1].file_id
    else:
        photo_file_id = None

    if photo_file_id:
        await _download_if_necessary(photo_file_id)
        return Image.open(f"/cache/{photo_file_id}")
