"""Module 2: Twitter/X API Client.

Manages Twitter API v2 for seed ingestion, polling, and posting.
Uses triple OAuth strategy:
- OAuth 1.0a (consumer_key + access_token): For POSTING tweets/replies
- OAuth 2.0 Bearer: For search/read endpoints
- OAuth 2.0 User Token: For Activity API subscriptions and elevated-scoped ops

tweepy handles rate limits automatically via wait_on_rate_limit=True.
Connection errors are retried with exponential backoff.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import httpx
import tweepy

from tap.config import Settings
from tap.exceptions import TwitterError
from tap.logger import get_logger
from tap.models import ActivitySubscriptionFilter, Tweet, TweetSource

log = get_logger("x_client")

# Maximum retry attempts for connection errors
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds

# X Activity API endpoints
_ACTIVITY_SUBSCRIPTIONS_URL = "https://api.x.com/2/activity/subscriptions"
_ACTIVITY_STREAM_URL = "https://api.x.com/2/activity/stream"


class TwitterClient:
    """Twitter API v2 client for TAP Framework.

    Uses tweepy.Client with triple OAuth:
    - OAuth 1.0a credentials for write operations (post_tweet, reply)
    - Bearer token for read operations (search, get mentions)
    - OAuth 2.0 User Token for Activity API subscriptions and elevated ops

    Rate limiting is handled automatically by tweepy (wait_on_rate_limit=True).
    Also provides Activity API subscription management for real-time
    event-driven monitoring with filter support.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize with tweepy client using triple OAuth.

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
        self._our_user_id: Optional[str] = None

        # OAuth 2.0 User Context client (for Activity API subscriptions)
        self._oauth2_token: Optional[str] = settings.twitter_oauth2_access_token
        self._oauth2_http: Optional[httpx.AsyncClient] = None

        log.info(
            "twitter_client_initialized",
            target=settings.target_handle,
            has_oauth2=bool(self._oauth2_token),
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
        # Ensure that every posted message contains "@hackinga0"
        if "@hackinga0" not in text.lower():
            if text and not text[-1].isspace():
                text = f"{text} @hackinga0"
            else:
                text = f"{text}@hackinga0"

        if reply_to_id and not reply_to_id.isdigit():
            log.warning(
                "post_probe_reply_to_id_non_numeric_ignoring",
                reply_to_id=reply_to_id,
            )
            reply_to_id = None

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
        if not self._target_user_id:
            await self._resolve_target_user_id()
        if not self._our_user_id:
            await self._resolve_our_user_id()

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

    async def _resolve_our_user_id(self) -> Optional[str]:
        """Resolve and cache our bot's user ID via Twitter API.

        Returns:
            Our bot user ID string, or None if resolution fails.
        """
        if self._our_user_id:
            return self._our_user_id

        if not self.settings.our_bot_handle:
            return None

        try:
            response = await self._retry(
                lambda: self.client.get_user(username=self.settings.our_bot_handle)
            )
            if response.data:
                self._our_user_id = str(response.data.id)
                log.info("our_user_id_resolved", user_id=self._our_user_id)
        except Exception as e:
            log.warning("our_user_id_resolution_failed", error=str(e))

        return self._our_user_id

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

        # Compare against cached our bot user ID
        if self._our_user_id and author_str == self._our_user_id:
            return TweetSource.OUR_BOT

        # Heuristic: username lookup is done in _search_tweets; here we only
        # have the ID. If target_user_id is not resolved yet, default to OTHER_USER.
        return TweetSource.OTHER_USER

    # =========================================================================
    # Activity API — Subscription Management (OAuth 2.0 User Context)
    # =========================================================================

    def _get_oauth2_headers(self) -> dict[str, str]:
        """Get HTTP headers for OAuth 2.0 User Context requests.

        Prefers the OAuth 2.0 User Access Token when available.
        Falls back to Bearer token for read-only access.

        Returns:
            Dictionary of HTTP headers.
        """
        token = self._oauth2_token or self.settings.twitter_bearer_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def create_activity_subscription(
        self,
        event_type: str = "post.create",
        subscription_filter: Optional[ActivitySubscriptionFilter] = None,
    ) -> dict:
        """Create an Activity API subscription for real-time event delivery.

        Uses OAuth 2.0 User Context (required for Activity API subscriptions).
        Supports filtered streams via ActivitySubscriptionFilter.

        Args:
            event_type: Event type to subscribe to. One of:
                'post.create', 'post.delete', 'chat.received', 'dm.received'.
            subscription_filter: Optional filter for keyword/user_id isolation.

        Returns:
            Subscription response dict from the API.

        Raises:
            TwitterError: If subscription creation fails.
        """
        body: dict = {"event_type": event_type}

        if subscription_filter:
            filter_dict: dict = {}
            if subscription_filter.user_ids:
                filter_dict["user_id"] = (
                    subscription_filter.user_ids[0]
                    if len(subscription_filter.user_ids) == 1
                    else subscription_filter.user_ids
                )
            if subscription_filter.keywords:
                filter_dict["keywords"] = subscription_filter.keywords
            if filter_dict:
                body["filter"] = filter_dict

        headers = self._get_oauth2_headers()

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                response = await client.post(
                    _ACTIVITY_SUBSCRIPTIONS_URL,
                    headers=headers,
                    json=body,
                )

                if response.status_code not in (200, 201):
                    raise TwitterError(
                        f"Subscription creation failed: {response.status_code} — {response.text[:200]}",
                        status_code=response.status_code,
                    )

                data = response.json()
                log.info(
                    "activity_subscription_created",
                    event_type=event_type,
                    has_filter=subscription_filter is not None,
                    response=data,
                )
                return data

        except httpx.HTTPError as e:
            raise TwitterError(
                f"Activity subscription HTTP error: {e}", original=e
            ) from e

    async def delete_activity_subscription(self, subscription_id: str) -> bool:
        """Delete an Activity API subscription.

        Args:
            subscription_id: The subscription ID to delete.

        Returns:
            True if deletion was successful.

        Raises:
            TwitterError: If deletion fails.
        """
        headers = self._get_oauth2_headers()
        url = f"{_ACTIVITY_SUBSCRIPTIONS_URL}/{subscription_id}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                response = await client.delete(url, headers=headers)

                if response.status_code not in (200, 204):
                    raise TwitterError(
                        f"Subscription deletion failed: {response.status_code} — {response.text[:200]}",
                        status_code=response.status_code,
                    )

                log.info("activity_subscription_deleted", subscription_id=subscription_id)
                return True

        except httpx.HTTPError as e:
            raise TwitterError(
                f"Subscription deletion HTTP error: {e}", original=e
            ) from e

    async def list_activity_subscriptions(self) -> list[dict]:
        """List all active Activity API subscriptions.

        Returns:
            List of subscription dicts.

        Raises:
            TwitterError: If listing fails.
        """
        headers = self._get_oauth2_headers()

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                response = await client.get(
                    _ACTIVITY_SUBSCRIPTIONS_URL,
                    headers=headers,
                )

                if response.status_code != 200:
                    raise TwitterError(
                        f"Subscription listing failed: {response.status_code} — {response.text[:200]}",
                        status_code=response.status_code,
                    )

                data = response.json()
                subscriptions = data.get("data", [])
                log.info("activity_subscriptions_listed", count=len(subscriptions))
                return subscriptions

        except httpx.HTTPError as e:
            raise TwitterError(
                f"Subscription listing HTTP error: {e}", original=e
            ) from e

    async def verify_crc(self, crc_token: str) -> dict:
        """Generate CRC response token for webhook verification.

        X requires this challenge-response for webhook URL verification.
        Uses the consumer secret to HMAC-SHA256 sign the crc_token.

        Args:
            crc_token: The crc_token from the X verification request.

        Returns:
            Dict with 'response_token' in the format 'sha256=<base64_hash>'.
        """
        consumer_secret = self.settings.twitter_consumer_secret
        sha256_hash = hmac.new(
            consumer_secret.encode("utf-8"),
            crc_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        response_token = base64.b64encode(sha256_hash).decode("utf-8")
        result = {"response_token": f"sha256={response_token}"}
        log.info("crc_verified")
        return result

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
