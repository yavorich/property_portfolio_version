def short_text(text: str, max_length: int):
    if len(text) <= max_length:
        return text
    else:
        return f"{text[:max_length-3]}..."
