import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def load_proxies() -> list[str | None]:
    """Return an ordered list of proxy URLs to try.

    Priority:
      1. ``TELEGRAM_PROXY_FILE`` — path to a text file with one proxy URL per line
         (blank lines and ``#`` comments are ignored).
      2. ``TELEGRAM_PROXY_URL`` — single proxy URL.
      3. No proxy (direct connection) — represented as ``[None]``.
    """

    proxy_file = getattr(settings, "TELEGRAM_PROXY_FILE", None)
    if proxy_file:
        path = Path(proxy_file)
        if path.is_file():
            proxies = _read_proxy_file(path)
            if proxies:
                logger.info("Loaded %d proxies from %s", len(proxies), path)
                return proxies
            logger.warning("Proxy file %s is empty, falling back to TELEGRAM_PROXY_URL", path)
        else:
            logger.warning("Proxy file %s not found, falling back to TELEGRAM_PROXY_URL", path)

    proxy_url = getattr(settings, "TELEGRAM_PROXY_URL", None)
    if proxy_url:
        return [proxy_url]

    return [None]


def _read_proxy_file(path: Path) -> list[str]:
    proxies: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        proxies.append(line)
    return proxies
