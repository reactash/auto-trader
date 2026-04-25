from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from data.news_data import fetch_stock_news, fetch_market_news
from engine.models import log_news_score
from utils.logger import logger

_analyzer = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def analyze_headline(headline: str) -> float:
    """Analyze a single headline. Returns VADER compound score (-1 to +1)."""
    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(headline)
    return scores["compound"]


def analyze_stock_sentiment(symbol: str, save_to_db: bool = True) -> float:
    """
    Fetch news for a symbol and return average sentiment score.
    Score > 0.05 = positive, < -0.05 = negative, else neutral.
    """
    news = fetch_stock_news(symbol)
    if not news:
        return 0.0

    scores = []
    for article in news:
        headline = article["headline"]
        score = analyze_headline(headline)
        scores.append(score)

        if save_to_db:
            log_news_score(
                symbol=symbol,
                headline=headline,
                sentiment_score=score,
                source=article.get("source", ""),
                url=article.get("url", ""),
            )

    avg_score = sum(scores) / len(scores) if scores else 0.0
    logger.debug(f"Sentiment for {symbol}: {avg_score:.3f} ({len(scores)} articles)")
    return avg_score


def analyze_multiple_stocks(symbols: list[str]) -> dict[str, float]:
    """Get sentiment scores for multiple symbols."""
    results = {}
    for symbol in symbols:
        results[symbol] = analyze_stock_sentiment(symbol)
    return results


def get_market_sentiment() -> float:
    """Get overall market mood from general market news."""
    news = fetch_market_news()
    if not news:
        return 0.0

    scores = [analyze_headline(article["headline"]) for article in news]
    avg = sum(scores) / len(scores)
    logger.info(f"Market sentiment: {avg:.3f} ({len(scores)} articles)")
    return avg
