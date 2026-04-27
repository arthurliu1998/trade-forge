import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from quantforge.monitor.news_scraper import NewsScraper, Article


class TestNewsScraper:
    def test_article_dataclass(self):
        a = Article(title="Test", text="Content", symbol="AAPL",
                    source="yahoo", url="http://example.com",
                    published="2026-04-27T08:00:00")
        assert a.symbol == "AAPL"
        assert a.source == "yahoo"

    def test_match_symbols_filters_by_watchlist(self):
        scraper = NewsScraper.__new__(NewsScraper)
        scraper.symbols = ["AAPL", "NVDA", "2330"]
        entries = [
            {"title": "AAPL earnings beat", "summary": "Apple reported...", "link": "http://a.com", "published": "now"},
            {"title": "Random stock news", "summary": "Nothing relevant", "link": "http://b.com", "published": "now"},
            {"title": "NVDA surges", "summary": "NVIDIA up 5%", "link": "http://c.com", "published": "now"},
        ]
        matched = scraper._match_symbols(entries)
        assert len(matched) == 2
        symbols = [a.symbol for a in matched]
        assert "AAPL" in symbols
        assert "NVDA" in symbols

    @pytest.mark.asyncio
    async def test_fetch_source_returns_articles(self):
        scraper = NewsScraper.__new__(NewsScraper)
        scraper.symbols = ["AAPL"]
        fake_feed = MagicMock()
        fake_feed.entries = [
            {"title": "AAPL up", "summary": "Apple rises", "link": "http://x.com", "published": "now"},
        ]
        with patch("quantforge.monitor.news_scraper.feedparser.parse", return_value=fake_feed):
            articles = await scraper._fetch_source("yahoo_finance", "http://example.com/rss")
        assert len(articles) == 1
        assert articles[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_fetch_all_aggregates_sources(self):
        scraper = NewsScraper(symbols=["AAPL"])
        with patch.object(scraper, "_fetch_source", new_callable=AsyncMock) as mock:
            mock.return_value = [
                Article("T", "C", "AAPL", "yahoo", "http://x.com", "now"),
            ]
            articles = await scraper.fetch_all()
        assert len(articles) >= 1
