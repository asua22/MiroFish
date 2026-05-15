"""
Financial News Extractor with mock data for local development
Optimized for testing without external dependencies
"""

import asyncio
import random
from typing import List, Optional
from datetime import datetime, timedelta
from ..models.data_extraction import NewsArticle
from ..utils.logger import get_logger

logger = get_logger('mirofish.extractors.news')


class NewsExtractor:
    """Extract financial news articles (mock data for testing)"""

    TRUSTED_SOURCES = {
        'Reuters': 'https://reuters.com',
        'Bloomberg': 'https://bloomberg.com',
        'CNBC': 'https://cnbc.com',
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        logger.info(f"NewsExtractor initialized with timeout={timeout}s")

    async def search_news(
        self,
        query: str,
        source_filter: Optional[List[str]] = None,
        time_range: str = "7d",
        limit: int = 10
    ) -> List[NewsArticle]:
        """
        Search and extract news articles (mock data)

        Args:
            query: Search query (ticker, keywords, etc)
            source_filter: List of specific sources
            time_range: Time range (1d, 7d, 30d)
            limit: Max articles to extract

        Returns:
            List of NewsArticle objects
        """
        logger.info(f"Searching news for: {query} (mock data)")

        query_lower = query.lower()

        # Mock articles database
        mock_articles = {
            'valuation': [
                {
                    'title': 'S&P 500 Valuations Reach Year-High on Earnings Beat',
                    'summary': 'Stock market valuations climbed to their highest levels this year as companies reported better-than-expected earnings results. Analysts debate whether current multiples are justified.',
                    'sentiment': 'positive',
                    'impact': 'high',
                    'assets': ['SPY', 'QQQ', 'IVV'],
                    'topics': ['stocks', 'earnings', 'valuation']
                },
                {
                    'title': 'Tech Sector Faces Valuation Pressure Amid Rate Concerns',
                    'summary': 'Technology stocks declined as investors reassess valuations in light of potential Federal Reserve rate hikes. Growth-heavy companies showing particular weakness.',
                    'sentiment': 'negative',
                    'impact': 'high',
                    'assets': ['NASDAQ', 'AAPL', 'MSFT', 'NVDA'],
                    'topics': ['stocks', 'interest_rates', 'valuation']
                },
                {
                    'title': 'Market Rally Driven by Improving Fundamentals and Valuations',
                    'summary': 'Equity markets surged today on strong economic data and reasonable valuations for quality companies. Investors showing renewed confidence in growth prospects.',
                    'sentiment': 'positive',
                    'impact': 'medium',
                    'assets': ['DIA', 'SPY'],
                    'topics': ['stocks', 'growth', 'market']
                },
            ],
            'stock': [
                {
                    'title': 'Major Tech Stocks Report Strong Q3 Earnings',
                    'summary': 'Large technology companies exceeded analyst expectations with robust revenue growth and margin expansion. Forward guidance suggests continued momentum.',
                    'sentiment': 'positive',
                    'impact': 'high',
                    'assets': ['AAPL', 'MSFT', 'GOOGL', 'META'],
                    'topics': ['earnings', 'stocks', 'tech']
                },
                {
                    'title': 'Banking Sector Volatility Creates Opportunities for Value Investors',
                    'summary': 'Recent swings in bank stocks have created attractive entry points for long-term investors. Analysts highlight improving net interest margins.',
                    'sentiment': 'neutral',
                    'impact': 'medium',
                    'assets': ['JPM', 'BAC', 'WFC', 'C'],
                    'topics': ['stocks', 'banking', 'valuation']
                },
            ],
            'market': [
                {
                    'title': 'Fed Decision Looms as Markets Digest Mixed Economic Data',
                    'summary': 'Investors await Federal Reserve announcement on interest rates following conflicting economic signals. Inflation data and employment figures suggest nuanced approach needed.',
                    'sentiment': 'neutral',
                    'impact': 'high',
                    'assets': ['DXY', 'TLT', 'IEF'],
                    'topics': ['fed', 'interest_rates', 'market']
                },
                {
                    'title': 'Global Markets Rally on Soft Landing Expectations',
                    'summary': 'International stock markets advanced as investors grow more confident in soft economic landing scenario. Economic data showing resilience despite rate hikes.',
                    'sentiment': 'positive',
                    'impact': 'medium',
                    'assets': ['VEA', 'VXUS', 'IEFA'],
                    'topics': ['market', 'growth', 'gdp']
                },
            ],
            'analysis': [
                {
                    'title': 'Market Analysis: Sector Rotation Accelerates',
                    'summary': 'Traditional sectors gaining favor over growth stocks as valuations reset. Energy and financials leading market breadth. Technical analysis suggests consolidation phase.',
                    'sentiment': 'neutral',
                    'impact': 'medium',
                    'assets': ['XLE', 'XLF', 'VTV'],
                    'topics': ['stocks', 'market', 'trading']
                },
            ]
        }

        # Find relevant articles based on query
        articles_to_use = []
        for keyword, articles in mock_articles.items():
            if keyword in query_lower or query_lower in keyword:
                articles_to_use.extend(articles)
                break

        if not articles_to_use:
            articles_to_use = [article for articles in mock_articles.values() for article in articles]

        # Create NewsArticle objects
        news_articles = []
        sources = source_filter or list(self.TRUSTED_SOURCES.keys())

        for i, article_data in enumerate(articles_to_use[:limit]):
            source = sources[i % len(sources)]

            article = NewsArticle(
                title=article_data['title'],
                source=source,
                url=f"https://{source.lower().replace(' ', '')}.com/news/{i}",
                published_at=datetime.utcnow() - timedelta(days=random.randint(0, 6)),
                content=article_data['summary'],
                summary=article_data['summary'],
                topics=article_data['topics'],
                sentiment=article_data['sentiment'],
                impact_level=article_data['impact'],
                mentioned_assets=article_data['assets'],
            )
            news_articles.append(article)

        logger.info(f"Generated {len(news_articles)} mock news articles for: {query}")
        return news_articles
