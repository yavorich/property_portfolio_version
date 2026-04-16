from dataclasses import dataclass, field
from typing import Protocol

import httpx


@dataclass
class ParsedListing:
    source: str
    source_url: str
    title: str = ""
    address: str = ""
    description: str = ""
    price: int | None = None
    currency: str = "AED"
    area_sqft: float | None = None
    area_sqm: float | None = None
    rooms: int | None = None
    bathrooms: int | None = None
    floor: str = ""
    broker_name: str = ""
    broker_phone: str = ""
    broker_email: str = ""
    broker_agency: str = ""
    photo_urls: list[str] = field(default_factory=list)
    raw_data: dict | None = None


class Parser(Protocol):
    SOURCE: str

    def __init__(self, http: httpx.AsyncClient) -> None: ...

    async def parse(self, url: str) -> ParsedListing: ...
