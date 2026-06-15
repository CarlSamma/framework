"""Module 2: Twitter/X API Client.

Manages Twitter API v2 for seed ingestion, polling, and posting.
Uses dual OAuth strategy:
- OAuth 1.0a (consumer_key + access_token): For POSTING tweets/replies
- OAuth 2.0 Bearer: For search/read endpoints

tweepy handles rate limits automatically via wait_on_rate_limit=True.
Connection errors are retried with exponential backoff.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import tweepy

from tap.config import Settings
from tap.exceptions import TwitterError
from tap.logger import get_logger
from tap.models import Tweet, TweetSource

log = get_logger("x_client")

# Maximum retry attempts for connection errors
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


class TwitterClient:
    """Twitter API v2 client for TAP Framework.

    Uses tweepy.Client with dual OAuth:
    - OAuth 1.0a credentials for write operations (post_tweet, reply)
    - Bearer token for read operations (search, get mentions)

    Rate limiting is handled automatically by tweepy (wait_on_rate_limit=True).
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize with tweepy client using dual OAuth.

        Args:
            settings: TAP Framework settings with Twitter credentials.
        """
        self.settings = settings
        self.client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            consumer_key=settings.twitter_consumer_key,
            consumer_secret=settings.twitter_consumer_secret,
            access_token=settings.twitter_access_token,
            access_token_secret=settings.twitter_access_token_secret,
            wait_on_rate_limit=True,
        )
        self._target_user_id: Optional[str] = None
        log.info(
            "twitter_client_initialized",
            target=settings.target_handle,
        )

    async def initialize_seed(self, limit: int = 100) -> list[Tweet]:
        """Fetch last `limit` tweets from/mentioning target. Reconstruct threads.

        Searches for tweets matching: to:HackingA0 OR from:HackingA0
        Then traces in_reply_to_tweet_id chains to reconstruct conversation threads.

        Args:
            limit: Maximum number of tweets to fetch.

        Returns:
            List of Tweet models, newest first.

        Raises:
            TwitterError: If API call fails after retries.
        """
        query = f"to:{self.settings.target_handle} OR from:{self.settings.target_handle}"
        try:
            tweets = await self._search_tweets(query=query, max_results=min(limit, 100))
            log.info("seed_ingested", count=len(tweets), query=query)
            return tweets
        except Exception as e:
            raise TwitterError(f"Failed to initialize seed: {e}", original=e) from e

    async def poll_new_tweets(self, since_id: Optional[str] = None) -> list[Tweet]:
        """Fetch new tweets since `since_id`.

        Args:
            since_id: Only return tweets with ID greater than this.

        Returns:
            List of new Tweet models.

        Raises:
            TwitterError: If API call fails.
        """
        query = f"to:{self.settings.target_handle} OR from:{self.settings.target_handle}"
        try:
            tweets = await self._search_tweets(
                query=query,
                max_results=100,
                since_id=since_id,
            )
            if tweets:
                log.info("new_tweets_polled", count=len(tweets), since_id=since_id)
            return tweets
        except Exception as e:
            raise TwitterError(f"Failed to poll tweets: {e}", original=e) from e

    async def post_probe(self, text: str, reply_to_id: Optional[str] = None) -> str:
        """Post a DPA-framed probe as a tweet or reply.

        Uses OAuth 1.0a user context (required for posting).

        Args:
            text: Tweet text content.
            reply_to_id: If replying, the tweet ID to reply to.

        Returns:
            The ID of the posted tweet as a string.

        Raises:
            TwitterError: If posting fails.
        """
        try:
            if reply_to_id:
                response = await self._retry(
                    lambda: self.client.create_tweet(
                        text=text,
                        in_reply_to_tweet_id=reply_to_id,
                    )
                )
            else:
                response = await self._retry(
                    lambda: self.client.create_tweet(text=text)
                )

            tweet_id = str(response.data["id"])
            log.info(
                "probe_posted",
                tweet_id=tweet_id,
                reply_to=reply_to_id,
                text_length=len(text),
            )
            return tweet_id
        except Exception as e:
            raise TwitterError(f"Failed to post probe: {e}", original=e) from e

    async def get_mentions(self, since_id: Optional[str] = None) -> list[Tweet]:
        """Get mentions of our bot handle.

        Args:
            since_id: Only return mentions with ID greater than this.

        Returns:
            List of Tweet models.

        Raises:
            TwitterError: If API call fails.
        """
        if not self.settings.our_bot_handle:
            log.warning("our_bot_handle_not_configured")
            return []

        try:
            # Get our bot's user ID first
            me = await self._retry(
                lambda: self.client.get_user(username=self.settings.our_bot_handle)
            )
            if not me.data:
                log.warning("our_bot_user_not_found", handle=self.settings.our_bot_handle)
                return []

            user_id = me.data.id
            response = await self._retry(
                lambda: self.client.get_users_mentions(
                    id=user_id,
                    since_id=since_id,
                    max_results=100,
                    tweet_fields=["created_at", "conversation_id", "in_reply_to_user_id"],
                )
            )

            if not response.data:
                return []

            tweets = []
            for tweet_data in response.data:
                tweet = Tweet(
                    id=str(tweet_data.id),
                    user_id=str(tweet_data.author_id) if hasattr(tweet_data, "author_id") else "",
                    username="",  # Will be populated if needed
                    text=tweet_data.text,
                    in_reply_to_tweet_id=str(tweet_data.in_reply_to_tweet_id)
                    if hasattr(tweet_data, "in_reply_to_tweet_id") and tweet_data.in_reply_to_tweet_id
                    else None,
                    created_at=tweet_data.created_at or datetime.now(timezone.utc),
                    source=TweetSource.OTHER_USER,
                    conversation_thread_id=str(tweet_data.conversation_id)
                    if hasattr(tweet_data, "conversation_id") and tweet_data.conversation_id
                    else None,
                )
                tweets.append(tweet)

            log.info("mentions_fetched", count=len(tweets))
            return tweets
        except Exception as e:
            raise TwitterError(f"Failed to get mentions: {e}", original=e) from e

    async def _search_tweets(
        self,
        query: str,
        max_results: int = 100,
        since_id: Optional[str] = None,
    ) -> list[Tweet]:
        """Search recent tweets using Twitter API v2.

        Args:
            query: Twitter search query.
            max_results: Max tweets to return (10-100).
            since_id: Only return tweets with ID greater than this.

        Returns:
            List of Tweet models.
        """
        response = await self._retry(
            lambda: self.client.search_recent_tweets(
                query=query,
                max_results=max_results,
                since_id=since_id,
                tweet_fields=["created_at", "conversation_id", "in_reply_to_user_id"],
                expansions=["author_id", "referenced_tweets.id"],
            )
        )

        if not response.data:
            return []

        # Build user lookup
        users = {}
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users[user.id] = user.username

        tweets = []
        for tweet_data in response.data:
            # Determine source
            source = self._classify_source(
                tweet_data.author_id,
                tweet_data.in_reply_to_user_id if hasattr(tweet_data, "in_reply_to_user_id") else None,
            )

            tweet = Tweet(
                id=str(tweet_data.id),
                user_id=str(tweet_data.author_id) if hasattr(tweet_data, "author_id") else "",
                username=users.get(tweet_data.author_id, "unknown") if hasattr(tweet_data, "author_id") else "unknown",
                text=tweet_data.text,
                in_reply_to_tweet_id=str(tweet_data.in_reply_to_tweet_id)
                if hasattr(tweet_data, "in_reply_to_tweet_id") and tweet_data.in_reply_to_tweet_id
                else None,
                created_at=tweet_data.created_at or datetime.now(timezone.utc),
                source=source,
                conversation_thread_id=str(tweet_data.conversation_id)
                if hasattr(tweet_data, "conversation_id") and tweet_data.conversation_id
                else None,
            )
            tweets.append(tweet)

        return tweets

    async def _resolve_target_user_id(self) -> Optional[str]:
        """Resolve and cache the target user's ID via Twitter API.

        Returns:
            Target user ID string, or None if resolution fails.
        """
        if self._target_user_id:
            return self._target_user_id

        try:
            response = await self._retry(
                lambda: self.client.get_user(username=self.settings.target_handle)
            )
            if response.data:
                self._target_user_id = str(response.data.id)
                log.info("target_user_id_resolved", user_id=self._target_user_id)
        except Exception as e:
            log.warning("target_user_id_resolution_failed", error=str(e))

        return self._target_user_id

    def _classify_source(
        self,
        author_id: Optional[int],
        in_reply_to_user_id: Optional[int] = None,
    ) -> TweetSource:
        """Classify a tweet's source based on author ID.

        Compares author_id against the cached target user ID.
        Falls back to OTHER_USER if target ID is not yet resolved.

        Args:
            author_id: The tweet author's user ID.
            in_reply_to_user_id: The user ID being replied to (unused).

        Returns:
            TweetSource classification.
        """
        if author_id is None:
            return TweetSource.OTHER_USER

        author_str = str(author_id)

        # Compare against cached target user ID
        if self._target_user_id and author_str == self._target_user_id:
            return TweetSource.TARGET_BOT

        # Heuristic: username lookup is done in _search_tweets; here we only
        # have the ID. If target_user_id is not resolved yet, default to OTHER_USER.
        return TweetSource.OTHER_USER

    async def _retry(self, func, max_retries: int = MAX_RETRIES):
        """Execute a synchronous tweepy call off the event loop with exponential backoff.

        Runs `func` in a ThreadPoolExecutor so blocking tweepy I/O does not
        stall the asyncio event loop.

        Args:
            func: Synchronous callable to execute.
            max_retries: Maximum retry attempts.

        Returns:
            Result of the function call.

        Raises:
            TwitterError: If all retries fail.
        """
        loop = asyncio.get_event_loop()
        last_error = None
        for attempt in range(max_retries):
            try:
                result = await loop.run_in_executor(None, func)
                return result
            except tweepy.TooManyRequests:
                # tweepy with wait_on_rate_limit=True should handle this,
                # but if it slips through, we re-raise
                raise
            except (tweepy.TweepyException, ConnectionError, TimeoutError) as e:
                last_error = e
                wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                log.warning(
                    "twitter_retry",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    wait_seconds=wait_time,
                    error=str(e),
                )
                await asyncio.sleep(wait_time)

        raise TwitterError(
            f"Twitter API call failed after {max_retries} retries",
            original=last_error,
        )
