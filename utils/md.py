import re

expression = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')


async def no_html(text: str) -> str:
    """
    Strips the text of any HTML tags.
    Called if the Telegram API doesn't accept our output.
    """
    text = re.sub(expression, '', text)
    return text
