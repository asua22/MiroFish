"""
Twitter/X Data Extractor using web scraping and mock data
Simplified for local development and testing
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import random
from ..models.data_extraction import TwitterUserProfile, Tweet, TwitterExtractionResponse
from ..utils.logger import get_logger

logger = get_logger('mirofish.extractors.twitter')


class TwitterExtractor:
    """Extract Twitter/X profile and tweet data using LLM-powered scraping"""
    
    def __init__(self, ollama_base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        """
        Initialize Twitter extractor with local Ollama
        
        Args:
            ollama_base_url: Ollama server URL (default: localhost:11434)
            model: LLM model name (default: qwen2.5:7b for 4GB VRAM)
        """
        self.ollama_base_url = ollama_base_url
        self.model = model
        self.session_cache = {}
        
        logger.info(f"TwitterExtractor initialized with model={model}, ollama_url={ollama_base_url}")
    
    async def extract_profile(self, username: str) -> Optional[TwitterUserProfile]:
        """
        Extract single Twitter profile data (mock data for local testing)

        Args:
            username: Twitter username (with or without @)

        Returns:
            TwitterUserProfile object or None if extraction failed
        """
        username = username.lstrip('@').lower()

        logger.info(f"Extracting profile: {username} (mock data)")

        try:
            # Mock profile data based on username
            mock_profiles = {
                'bloomberg': {
                    'name': 'Bloomberg',
                    'bio': 'Real-time financial information and market analysis',
                    'followers_count': 5200000,
                    'following_count': 1200,
                    'tweet_count': 150000,
                    'verified': True,
                    'location': 'New York, NY',
                    'website': 'www.bloomberg.com'
                },
                'reuters': {
                    'name': 'Reuters',
                    'bio': 'News and insights on markets, business and world news',
                    'followers_count': 4800000,
                    'following_count': 1500,
                    'tweet_count': 140000,
                    'verified': True,
                    'location': 'London, UK',
                    'website': 'www.reuters.com'
                },
                'cnbc': {
                    'name': 'CNBC',
                    'bio': 'Business news and analysis from CNBC',
                    'followers_count': 3200000,
                    'following_count': 1800,
                    'tweet_count': 120000,
                    'verified': True,
                    'location': 'New York, NY',
                    'website': 'www.cnbc.com'
                },
            }

            # Get mock data or generate random profile
            profile_data = mock_profiles.get(username, {
                'name': username.title(),
                'bio': f'Financial analyst and market commentator @{username}',
                'followers_count': random.randint(50000, 500000),
                'following_count': random.randint(500, 5000),
                'tweet_count': random.randint(10000, 100000),
                'verified': random.choice([True, False]),
                'location': random.choice(['New York', 'London', 'Singapore', 'Hong Kong']),
                'website': f'https://{username}.com'
            })

            profile = TwitterUserProfile(
                username=username,
                name=profile_data.get('name', username),
                bio=profile_data.get('bio', ''),
                followers_count=profile_data.get('followers_count', 0),
                following_count=profile_data.get('following_count', 0),
                tweet_count=profile_data.get('tweet_count', 0),
                verified=profile_data.get('verified', False),
                profile_url=f"https://x.com/{username}",
                location=profile_data.get('location'),
                website=profile_data.get('website'),
            )

            logger.info(f"Successfully created mock profile: {username}")
            return profile

        except Exception as e:
            logger.error(f"Error extracting profile {username}: {str(e)}")
            return None
    
    async def extract_tweets(self, username: str, limit: int = 10) -> List[Tweet]:
        """
        Extract recent tweets from user timeline (mock data for testing)

        Args:
            username: Twitter username
            limit: Max number of tweets to extract (max 50)

        Returns:
            List of Tweet objects
        """
        username = username.lstrip('@').lower()
        limit = min(limit, 50)

        logger.info(f"Extracting {limit} tweets from @{username} (mock data)")

        try:
            # Mock tweets data
            sample_tweets = {
                'bloomberg': [
                    'Market volatility increases as Fed signals potential rate changes',
                    'Tech stocks decline following earnings disappointment',
                    'Gold prices rise amid economic uncertainty',
                    'Oil markets stabilize after supply concerns resolved',
                ],
                'reuters': [
                    'Central banks coordinate response to inflation pressures',
                    'Corporate profits exceed expectations in Q3 earnings',
                    'Emerging markets face currency headwinds',
                    'Trade tensions impact global supply chains',
                ],
                'cnbc': [
                    'Stock market reaches new highs on positive economic data',
                    'Inflation trends show gradual improvement',
                    'Fed officials debate timing of policy decisions',
                    'Investors rebalance portfolios ahead of earnings season',
                ]
            }

            username_tweets = sample_tweets.get(username, [
                'Market analysis shows interesting trends ahead',
                'Recent economic data suggests continued growth',
                'Investment opportunities emerging in multiple sectors',
                'Risk management remains critical in current environment',
            ])

            tweets = []
            sentiment_options = ['positive', 'negative', 'neutral']
            topic_options = ['markets', 'economics', 'stocks', 'finance', 'trading', 'valuations']

            for i in range(min(limit, len(username_tweets))):
                tweet = Tweet(
                    tweet_id=f"tw_{i:08d}",
                    author=username,
                    text=username_tweets[i],
                    created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
                    likes=random.randint(100, 10000),
                    retweets=random.randint(50, 5000),
                    replies=random.randint(20, 2000),
                    sentiment=random.choice(sentiment_options),
                    topics=[random.choice(topic_options) for _ in range(random.randint(1, 3))],
                )
                tweets.append(tweet)

            logger.info(f"Created {len(tweets)} mock tweets from @{username}")
            return tweets

        except Exception as e:
            logger.error(f"Error extracting tweets from {username}: {str(e)}")
            return []
    
    async def extract_search_results(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Extract profiles and tweets from search results (mock data for testing)

        Args:
            query: Search query
            limit: Max profiles to extract (1-20)

        Returns:
            Dictionary with profiles and top tweets
        """
        query_lower = query.lower()
        limit = min(limit, 20)

        logger.info(f"Extracting search results for query: {query} (mock data)")

        try:
            # Mock profiles and tweets based on query
            profiles_map = {
                'valuation': ['bloomberg', 'reuters', 'cnbc'],
                'stock': ['marketwatch', 'investor', 'trader'],
                'analysis': ['analyst1', 'analyst2', 'analyst3'],
            }

            # Determine which profiles to return based on query
            relevant_profiles = []
            for keyword, profiles in profiles_map.items():
                if keyword in query_lower:
                    relevant_profiles.extend(profiles)
                    break

            if not relevant_profiles:
                relevant_profiles = ['bloomberg', 'reuters', 'cnbc']

            # Generate mock profile data
            top_profiles = []
            for profile_name in relevant_profiles[:limit]:
                profile_data = {
                    'username': profile_name,
                    'name': profile_name.title() + ' Analyst' if len(profile_name) < 10 else profile_name.title(),
                    'bio': f'Financial analysis and market commentary about {query}',
                    'profile_url': f'https://x.com/{profile_name}'
                }
                top_profiles.append(profile_data)

            # Generate mock tweets
            relevant_tweets = []
            tweet_templates = [
                f'Latest analysis on {query}: Market indicators suggest...',
                f'{query} showing interesting patterns for investors',
                f'Key insights about {query} in today\'s market',
                f'Market reaction to {query} developments',
                f'{query} analysis: What it means for your portfolio',
            ]

            for i, template in enumerate(tweet_templates[:limit]):
                tweet_data = {
                    'author': relevant_profiles[i % len(relevant_profiles)],
                    'text': template,
                    'created_at': (datetime.utcnow() - timedelta(hours=random.randint(1, 48))).isoformat(),
                    'sentiment': random.choice(['positive', 'negative', 'neutral']),
                    'likes': random.randint(200, 5000),
                    'retweets': random.randint(100, 2000),
                }
                relevant_tweets.append(tweet_data)

            result = {
                'top_profiles': top_profiles,
                'relevant_tweets': relevant_tweets
            }

            logger.info(f"Generated mock search results for: {query}")
            return result
            
        except Exception as e:
            logger.error(f"Error searching for {query}: {str(e)}")
            return {"top_profiles": [], "relevant_tweets": []}
    
    async def batch_extract_profiles(self, usernames: List[str]) -> List[TwitterUserProfile]:
        """
        Extract multiple profiles with batching (2-3 at a time for 4GB VRAM)
        
        Args:
            usernames: List of Twitter usernames
            
        Returns:
            List of extracted profiles
        """
        logger.info(f"Batch extracting {len(usernames)} profiles (batch size: 2-3)")
        
        profiles = []
        batch_size = 2  # Conservative for 4GB VRAM
        
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i+batch_size]
            batch_results = await asyncio.gather(
                *[self.extract_profile(u) for u in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, TwitterUserProfile):
                    profiles.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Batch extraction error: {str(result)}")
            
            # Small delay between batches to avoid overwhelming local LLM
            if i + batch_size < len(usernames):
                await asyncio.sleep(2)
        
        return profiles