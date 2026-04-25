import feedparser
from gnews import GNews

from utils.logger import logger


_gnews_client = None


def _get_gnews_client() -> GNews:
    global _gnews_client
    if _gnews_client is None:
        _gnews_client = GNews(
            language="en",
            country="US",
            max_results=10,
            period="1d",
        )
    return _gnews_client


# US financial news RSS feeds
RSS_FEEDS = {
    "CNBC Markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
}


def fetch_stock_news(symbol: str, max_results: int = 10) -> list[dict]:
    """Fetch recent news for a specific stock symbol."""
    client = _get_gnews_client()
    try:
        results = client.get_news(f"{symbol} stock")
        news = []
        for item in results[:max_results]:
            news.append({
                "headline": item.get("title", ""),
                "source": item.get("publisher", {}).get("title", "Unknown"),
                "published_at": item.get("published date", ""),
                "url": item.get("url", ""),
                "symbol": symbol,
            })
        logger.debug(f"Fetched {len(news)} news articles for {symbol}")
        return news
    except Exception as e:
        logger.error(f"Failed to fetch news for {symbol}: {e}")
        return []


def fetch_market_news(max_results: int = 20) -> list[dict]:
    """Fetch general US market news from GNews + RSS feeds."""
    news = []

    # GNews
    client = _get_gnews_client()
    try:
        results = client.get_news("US stock market trading")
        for item in results[:max_results // 2]:
            news.append({
                "headline": item.get("title", ""),
                "source": item.get("publisher", {}).get("title", "Unknown"),
                "published_at": item.get("published date", ""),
                "url": item.get("url", ""),
                "symbol": "MARKET",
            })
    except Exception as e:
        logger.error(f"GNews market news fetch failed: {e}")

    # RSS feeds
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                news.append({
                    "headline": entry.get("title", ""),
                    "source": source_name,
                    "published_at": entry.get("published", ""),
                    "url": entry.get("link", ""),
                    "symbol": "MARKET",
                })
        except Exception as e:
            logger.error(f"RSS feed {source_name} failed: {e}")

    logger.info(f"Fetched {len(news)} market news articles")
    return news


def fetch_news_for_symbols(symbols: list[str], max_per_symbol: int = 5) -> dict[str, list[dict]]:
    """Fetch news for multiple symbols. Returns dict of symbol -> news list."""
    result = {}
    for symbol in symbols:
        result[symbol] = fetch_stock_news(symbol, max_per_symbol)
    return result
