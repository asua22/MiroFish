"""
Data Extraction Module - Twitter, News, and other data sources
"""

from .twitter_extractor import TwitterExtractor
from .news_extractor import NewsExtractor

__all__ = ['TwitterExtractor', 'NewsExtractor']