from urllib.parse import urlparse

import httpx

from .base import ParsedListing, Parser
from .bayut import BayutParser
from .property_finder import PropertyFinderParser


class ParserNotFound(Exception):
    pass


_REGISTRY: dict[str, type[Parser]] = {
    "bayut.com": BayutParser,
    "www.bayut.com": BayutParser,
    "propertyfinder.ae": PropertyFinderParser,
    "www.propertyfinder.ae": PropertyFinderParser,
}


def get_parser(url: str, http: httpx.AsyncClient) -> Parser:
    host = (urlparse(url).hostname or "").lower()
    cls = _REGISTRY.get(host)
    if not cls:
        raise ParserNotFound(f"No parser for host {host!r}")
    return cls(http)


__all__ = [
    "ParsedListing",
    "Parser",
    "ParserNotFound",
    "get_parser",
]
