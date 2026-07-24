"""
=============================================================================
Organic Marketing AI — Twitter/X API v2 Service (Tweepy)
=============================================================================
Automated Twitter/X publishing via the v2 API. Supports single tweets
and multi-tweet threads for educational content.

Required environment variables:
  - TWITTER_API_KEY
  - TWITTER_API_SECRET
  - TWITTER_ACCESS_TOKEN
  - TWITTER_ACCESS_TOKEN_SECRET

Twitter Developer Portal must have "Read and Write" permissions enabled.
=============================================================================
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from database import AsyncSessionLocal, SocialConnection
from sqlalchemy import select
from services.crypto_service import decrypt_token

logger = logging.getLogger("organicai.twitter")


class TwitterService:
    """
    Twitter/X v2 API client for automated posting.
    Uses tweepy for OAuth 1.0a User Context authentication.
    """

    def __init__(self):
        self.api_key = os.getenv("TWITTER_API_KEY", "")
        self.api_secret = os.getenv("TWITTER_API_SECRET", "")

    async def _get_client(self, workspace_id: str):
        """Initialize the tweepy Client for a specific tenant."""
        if not self.api_key or not self.api_secret:
            logger.warning("Twitter API platform credentials not configured.")
            return None

        async with AsyncSessionLocal() as session:
            stmt = select(SocialConnection).where(SocialConnection.businessProfileId == workspace_id)
            conn = (await session.execute(stmt)).scalars().first()
            if not conn or not conn.twitterAccessToken or not conn.twitterAccessSecret:
                logger.warning(f"No Twitter credentials for workspace {workspace_id}")
                return None
            
            access_token = decrypt_token(conn.twitterAccessToken) or conn.twitterAccessToken
            access_token_secret = decrypt_token(conn.twitterAccessSecret) or conn.twitterAccessSecret

        try:
            import tweepy  # noqa: F811
            client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
            )
            return client
        except ImportError:
            logger.warning("tweepy package not installed — Twitter integration disabled.")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            return None

    async def post_tweet(self, workspace_id: str, text: str) -> Optional[str]:
        """
        Post a single tweet. Returns the tweet ID on success.
        
        Args:
            text: Tweet content (max 280 chars for free tier, 25,000 for Premium+)
        
        Returns:
            Tweet ID string, or None on failure.
        """
        client = await self._get_client(workspace_id)
        if not client:
            return None

        try:
            response = client.create_tweet(text=text)
            tweet_id = response.data["id"]
            logger.info(f"Tweet posted successfully: {tweet_id}")
            return str(tweet_id)
        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            return None

    async def post_thread(self, workspace_id: str, tweets: list[str]) -> list[str]:
        """
        Post a multi-tweet thread. Each tweet is chained via in_reply_to_tweet_id.
        
        Args:
            tweets: List of tweet texts, in order. First tweet is the root.
        
        Returns:
            List of tweet IDs posted, or empty list on failure.
        """
        client = await self._get_client(workspace_id)
        if not client or not tweets:
            return []

        posted_ids: list[str] = []
        reply_to: Optional[str] = None

        try:
            for i, text in enumerate(tweets):
                kwargs = {"text": text}
                if reply_to:
                    kwargs["in_reply_to_tweet_id"] = reply_to

                response = client.create_tweet(**kwargs)
                tweet_id = str(response.data["id"])
                posted_ids.append(tweet_id)
                reply_to = tweet_id
                logger.info(f"Thread tweet {i + 1}/{len(tweets)} posted: {tweet_id}")

            logger.info(f"Full thread posted: {len(posted_ids)} tweets.")
            return posted_ids
        except Exception as e:
            logger.error(f"Thread posting failed at tweet {len(posted_ids) + 1}: {e}")
            return posted_ids

    async def generate_thread_from_caption(self, caption: str, hashtags: str = "") -> list[str]:
        """
        Split a long-form caption into a Twitter thread (max 280 chars per tweet).
        Appends hashtags to the final tweet only.
        
        Args:
            caption: Full marketing copy / educational content.
            hashtags: Hashtags string to append to the last tweet.
        
        Returns:
            List of tweet-sized strings.
        """
        max_len = 275  # Leave room for thread indicators
        words = caption.split()
        tweets: list[str] = []
        current = ""

        for word in words:
            if len(current) + len(word) + 1 > max_len:
                tweets.append(current.strip())
                current = word
            else:
                current = f"{current} {word}" if current else word

        if current.strip():
            tweets.append(current.strip())

        # Append hashtags to the last tweet
        if hashtags and tweets:
            last = tweets[-1]
            if len(last) + len(hashtags) + 2 <= 280:
                tweets[-1] = f"{last}\n\n{hashtags}"
            else:
                tweets.append(hashtags)

        # Add thread indicators (1/N, 2/N, etc.)
        if len(tweets) > 1:
            total = len(tweets)
            tweets = [f"{t} ({i + 1}/{total})" for i, t in enumerate(tweets)]

        return tweets


# ─── Singleton ───────────────────────────────────────────────────────
twitter_service = TwitterService()
