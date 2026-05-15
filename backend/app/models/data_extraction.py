"""
Data Extraction Models - Pydantic schemas for Twitter/News data validation
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============= Twitter/X Data Models =============

class TwitterUserProfile(BaseModel):
    """Individual Twitter user profile extracted from tweet/profile page"""
    username: str = Field(..., description="Twitter handle (without @)")
    name: str = Field(..., description="Display name")
    bio: str = Field(..., description="User bio/description")
    followers_count: Optional[int] = Field(0, description="Number of followers")
    following_count: Optional[int] = Field(0, description="Number of following")
    tweet_count: Optional[int] = Field(0, description="Total tweets")
    verified: bool = Field(False, description="Is verified account")
    profile_url: str = Field(..., description="Profile URL")
    avatar_url: Optional[str] = Field(None, description="Avatar/profile image URL")
    location: Optional[str] = Field(None, description="User location")
    website: Optional[str] = Field(None, description="Website link in bio")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "elonmusk",
                "name": "Elon Musk",
                "bio": "Engineer, entrepreneur, investor",
                "followers_count": 150000000,
                "verified": True,
                "profile_url": "https://twitter.com/elonmusk"
            }
        }


class Tweet(BaseModel):
    """Single tweet for sentiment/impact analysis"""
    tweet_id: str = Field(..., description="Unique tweet ID")
    author: str = Field(..., description="Tweet author username")
    text: str = Field(..., description="Tweet content")
    created_at: datetime = Field(..., description="Tweet creation timestamp")
    likes: int = Field(0, description="Like count")
    retweets: int = Field(0, description="Retweet count")
    replies: int = Field(0, description="Reply count")
    sentiment: Optional[str] = Field(None, description="Detected sentiment: positive/negative/neutral")
    topics: Optional[List[str]] = Field([], description="Topics mentioned (stocks, crypto, etc)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tweet_id": "1234567890",
                "author": "elonmusk",
                "text": "Tesla stock price too high imo",
                "created_at": "2024-01-15T10:30:00Z",
                "sentiment": "negative",
                "topics": ["TSLA", "stock"]
            }
        }


class TwitterExtractionRequest(BaseModel):
    """Request to extract Twitter data"""
    query: str = Field(..., description="Search query or username to extract")
    extract_type: str = Field("profile", description="Type: 'profile' or 'search'")
    limit: int = Field(10, description="Max number of results (1-50)")
    include_tweets: bool = Field(True, description="Include recent tweets from user/search")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "elonmusk",
                "extract_type": "profile",
                "limit": 10
            }
        }


class TwitterExtractionResponse(BaseModel):
    """Response with extracted Twitter data"""
    success: bool
    extraction_id: str = Field(..., description="Unique extraction session ID")
    status: str = Field(..., description="Status: pending/processing/completed/failed")
    profiles: List[TwitterUserProfile] = Field([], description="Extracted user profiles")
    tweets: List[Tweet] = Field([], description="Extracted tweets")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = Field(None, description="Error message if extraction failed")


# ============= News Data Models =============

class NewsArticle(BaseModel):
    """Single news article for market sentiment analysis"""
    title: str = Field(..., description="Article headline")
    source: str = Field(..., description="News source name")
    url: str = Field(..., description="Article URL")
    published_at: datetime = Field(..., description="Publication timestamp")
    content: str = Field(..., description="Article body text")
    summary: Optional[str] = Field(None, description="Auto-generated summary")
    topics: List[str] = Field([], description="Topics: stocks, crypto, markets, etc")
    sentiment: Optional[str] = Field(None, description="Article sentiment: positive/negative/neutral")
    impact_level: Optional[str] = Field(None, description="Market impact: high/medium/low")
    mentioned_assets: Optional[List[str]] = Field([], description="Tickers mentioned: AAPL, BTC, etc")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Fed Raises Interest Rates",
                "source": "Reuters",
                "url": "https://reuters.com/article/fed",
                "published_at": "2024-01-15T09:00:00Z",
                "content": "Federal Reserve announced...",
                "topics": ["Fed", "interest_rates", "market"],
                "sentiment": "negative",
                "impact_level": "high",
                "mentioned_assets": ["SPY", "QQQ"]
            }
        }


class NewsExtractionRequest(BaseModel):
    """Request to extract financial news"""
    query: str = Field(..., description="Search query: ticker, topic, or keywords")
    sources: Optional[List[str]] = Field(
        default=None, 
        description="Filter by news sources (Reuters, Bloomberg, etc). None = all"
    )
    time_range: str = Field("7d", description="Time range: 1d, 7d, 30d")
    limit: int = Field(10, description="Max number of articles (1-50)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Fed interest rates",
                "time_range": "7d",
                "limit": 10
            }
        }


class NewsExtractionResponse(BaseModel):
    """Response with extracted news articles"""
    success: bool
    extraction_id: str = Field(..., description="Unique extraction session ID")
    status: str = Field(..., description="Status: pending/processing/completed/failed")
    articles: List[NewsArticle] = Field([], description="Extracted articles")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    total_found: int = Field(0, description="Total articles found (may exceed limit)")
    error: Optional[str] = Field(None, description="Error message if extraction failed")


# ============= Data Selection for Simulation =============

class SelectedProfile(BaseModel):
    """User profile selected for simulation - combines Twitter + context"""
    source: str = Field("twitter", description="Data source: twitter, manual_input")
    username: str = Field(..., description="Username/handle")
    name: str = Field(..., description="Display name")
    bio: str = Field(..., description="Bio/description")
    personality_traits: Optional[List[str]] = Field(
        [], 
        description="Extracted or manual personality traits"
    )
    behavior_style: Optional[str] = Field(
        None,
        description="Behavior: aggressive, cautious, analytical, emotional"
    )
    risk_tolerance: Optional[str] = Field(
        None,
        description="Risk level: high, medium, low"
    )
    recent_tweets: Optional[List[str]] = Field(
        [],
        description="Recent tweets for behavior pattern analysis"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata from extraction"
    )


class SimulationDataPackage(BaseModel):
    """Complete data package ready for simulation"""
    session_id: str = Field(..., description="Unique session ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    profiles: List[SelectedProfile] = Field(..., description="Agent profiles for simulation")
    market_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Market context from news extraction"
    )
    news_articles: List[NewsArticle] = Field(
        [],
        description="News articles for sentiment initialization"
    )
    simulation_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Simulation parameters"
    )
