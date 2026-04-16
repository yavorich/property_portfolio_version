import httpx

from .base import ParsedListing


class PropertyFinderParser:
    """Property Finder parser — implementation pending."""

    SOURCE = "property_finder"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def parse(self, url: str) -> ParsedListing:
        raise NotImplementedError(
            "Парсер Property Finder ещё не реализован."
        )
