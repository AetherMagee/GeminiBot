import os

from aiogram.types import Message
from loguru import logger
from PIL import Image

from main import bot


async def _download_if_necessary(file_id: str):
    if not os.path.exists(f"/cache/{file_id}"):
        logger.debug(f"Downloading {file_id}")
        await bot.download(file_id, f"/cache/{file_id}")


async def extract_media_artifacts(message: Message) -> list:
    media_artifacts = []

    # Photos
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo[-1].file_id
    else:
        photo_file_id = None

    if photo_file_id:
        await _download_if_necessary(photo_file_id)
        media_artifacts.append(Image.open(f"/cache/{photo_file_id}"))

    # Audio
    if message.audio:
        if message.audio.file_size < 10_000_000:
            audio_file_id = message.audio.file_id
        else:
            audio_file_id = None
    else:
        audio_file_id = None

    if audio_file_id:
        await _download_if_necessary(audio_file_id)
        with open(f"/cache/{audio_file_id}", "rb") as audio_file:
            media_artifacts.append(audio_file)

    # Video
    if message.video:
        if message.video.file_size < 10_000_000:
            video_file_id = message.video.file_id
        else:
            video_file_id = None
    else:
        video_file_id = None

    if video_file_id:
        await _download_if_necessary(video_file_id)
        with open(f"/cache/{video_file_id}", "rb") as video_file:
            media_artifacts.append(video_file)

    return media_artifacts
