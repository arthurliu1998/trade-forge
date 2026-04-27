"""Fetch news from 6 RSS sources, filter for watchlist symbols."""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    text: str
    symbol: str
    source: str
    url: str
    published: str


SOURCES = [
    ("yahoo_finance", "https://finance.yahoo.com/news/rssindex"),
    ("finviz", "https://finviz.com/news_export.ashx?v=3"),
    ("google_news", "https://news.google.com/rss/search?q=stock+market"),
    ("cnyes", "https://news.cnyes.com/rss"),
    ("moneydj", "https://www.moneydj.com/rss/rsscategory.djrss?a=latest"),
    ("twse", "https://mops.twse.com.tw/mops/web/ajax_t05st01"),
]


class NewsScraper:
    def __init__(self, symbols: list[str] = None, sources: list[tuple] = None):
        self.symbols = [s.upper() for s in (symbols or [])]
        self.sources = sources or SOURCES

    async def fetch_all(self) -> list[Article]:
        tasks = [
            self._fetch_source(name, url)
            for name, url in self.sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Source fetch failed: %s", type(result).__name__)
                continue
            articles.extend(result)
        return articles

    async def _fetch_source(self, source_name: str, url: str) -> list[Article]:
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            entries = feed.entries if hasattr(feed, "entries") else []
            return self._match_symbols(entries, source_name)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", source_name, type(e).__name__)
            return []

    def _match_symbols(self, entries: list, source_name: str = "") -> list[Article]:
        articles = []
        for entry in entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            combined = f"{title} {summary}".upper()
            for sym in self.symbols:
                if sym in combined:
                    articles.append(Article(
                        title=title,
                        text=summary,
                        symbol=sym,
                        source=source_name,
                        url=entry.get("link", ""),
                        published=entry.get("published", ""),
                    ))
                    break
        return articles
