from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from sherpa.config import Settings, get_settings
from sherpa.providers.base import NewsItem, NewsProvider

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"


class NewsRSSProvider:
    """
    Free-tier friendly: Google News RSS search by ticker (no API key).
    Rate-limit friendly: keep limit small and cache at call site if needed.
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0, follow_redirects=True)

    def headlines_for_symbol(self, symbol: str, *, limit: int = 15) -> list[NewsItem]:
        q = quote(f"{symbol} stock")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        try:
            r = self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("RSS fetch failed for %s: %s", symbol, e)
            return []
        return _parse_google_news_rss(r.text, limit=limit)


class NewsAPIProvider:
    """Paid / free-dev tier: https://newsapi.org — set NEWS_API_KEY."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.Client(timeout=30.0)

    def headlines_for_symbol(self, symbol: str, *, limit: int = 15) -> list[NewsItem]:
        params = {
            "q": f'"{symbol}" AND (stock OR shares OR earnings)',
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(limit, 100),
            "apiKey": self._key,
        }
        try:
            r = self._client.get(NEWSAPI_URL, params=params)
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("NewsAPI failed for %s: %s", symbol, e)
            return []
        data = r.json()
        articles = data.get("articles") or []
        out: list[NewsItem] = []
        for a in articles[:limit]:
            pub = a.get("publishedAt") or ""
            try:
                published_at = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except ValueError:
                published_at = datetime.now(timezone.utc)
            out.append(
                NewsItem(
                    published_at=published_at,
                    title=str(a.get("title") or ""),
                    source=str((a.get("source") or {}).get("name") or "newsapi"),
                    url=a.get("url"),
                    summary=a.get("description"),
                )
            )
        return out


def _parse_google_news_rss(xml_text: str, *, limit: int) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    items: list[NewsItem] = []
    for item in channel.findall("item")[:limit]:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        source_el = item.find("source")
        title = (title_el.text or "").strip() if title_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else None
        pub_raw = (pub_el.text or "").strip() if pub_el is not None else ""
        try:
            published_at = parsedate_to_datetime(pub_raw)
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published_at = datetime.now(timezone.utc)
        src = (source_el.text or "google_news").strip() if source_el is not None else "google_news"
        items.append(
            NewsItem(
                published_at=published_at,
                title=title,
                source=src,
                url=link,
            )
        )
    return items


def create_news_provider(settings: Settings | None = None) -> NewsProvider:
    s = settings or get_settings()
    if s.news_api_key:
        return NewsAPIProvider(s.news_api_key)
    return NewsRSSProvider()
