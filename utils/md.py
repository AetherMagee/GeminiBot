async def no_markdown(text: str) -> str:
    """
    Strips the text of any markdown-related characters.
    Called if the Telegram API doesn't accept our output.
    """
    forbidden_characters = ['*', '_', ']', '[', '`', '\\']
    for character in forbidden_characters:
        text = text.replace(character, '')
    return text
