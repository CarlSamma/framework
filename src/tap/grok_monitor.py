"""Module 8: Grok Monitor (via OpenRouter).

Monitors target's Twitter activity and analyzes responses using Grok via OpenRouter.
Uses the openai client pointing at OpenRouter's OpenAI-compatible API.

Architecture:
- Tweet fetching: TwitterClient (tweepy + Twitter API v2)
- Response analysis: GrokMonitor (Grok via OpenRouter)
- Single API key (OPENROUTER_API_KEY) for all LLM operations

Grok is used purely as an LLM for analyzing responses and generating
structured intelligence — NOT for x_search (that uses Twitter API v2).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from openai import AsyncOpenAI

from tap.config import Settings
from tap.exceptions import LLMError, TwitterError
from tap.logger import get_logger
from tap.models import GrokAnalysis, OtherUserIntel, Tweet, TweetSource
from tap.prompts import GROK_ANALYZER_SYSTEM, GROK_ANALYZER_USER
from tap.x_client import TwitterClient

log = get_logger("grok_monitor")


class GrokMonitor:
    """Monitors @HackingA0 via Grok (through OpenRouter).

    Uses Grok (x-ai/grok-4) via OpenRouter's OpenAI-compatible API for
    structured response analysis. Tweet fetching is handled by TwitterClient.
    """

    # Manually injected responses for sandboxing
    mock_replies: dict[str, str] = {}
    pending_tweet_id: Optional[str] = None

    def __init__(self, settings: Settings, twitter: TwitterClient) -> None:
        """Initialize Grok monitor.

        Args:
            settings: TAP Framework settings.
            twitter: Twitter API v2 client.
        """
        self.settings = settings
        self.twitter = twitter
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
        self.model = settings.openrouter_model_grok
        log.info("grok_monitor_initialized", model=self.model)

    async def search_recent(
        self,
        since_date: Optional[str] = None,
        handles: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search recent tweets from target using Twitter API v2.

        Args:
            since_date: Only return tweets after this date (ISO format).
            handles: List of handles to search (default: ["HackingA0"]).

        Returns:
            List of tweet dictionaries with text, author, date, etc.
        """
        if not self.twitter:
            log.warning("no_twitter_client_configured")
            return []

        try:
            tweets = await self.twitter.poll_new_tweets()
            return [
                {
                    "id": t.id,
                    "text": t.text,
                    "username": t.username,
                    "created_at": t.created_at.isoformat(),
                    "source": t.source.value,
                }
                for t in tweets
            ]
        except TwitterError as e:
            log.error("grok_search_failed", error=str(e))
            return []

    async def wait_for_reply(
        self,
        tweet_id: str,
        timeout: int = 3600,
    ) -> Optional[Tweet]:
        """Wait for target to reply to our tweet. Poll every 30s.

        Args:
            tweet_id: The ID of our tweet to wait for a reply to.
            timeout: Maximum wait time in seconds (default: 3600 = 1 hour).

        Returns:
            The reply Tweet model if found, None if timeout.
        """
        if not self.twitter:
            log.warning("no_twitter_client_for_reply_wait")
            return None

        poll_interval = self.settings.poll_interval_seconds
        elapsed = 0
        consecutive_errors = 0

        # Register pending tweet ID
        GrokMonitor.pending_tweet_id = tweet_id

        log.info("waiting_for_reply", tweet_id=tweet_id, timeout=timeout)

        while elapsed < timeout:
            # Check for manually injected mock reply first
            if tweet_id in GrokMonitor.mock_replies:
                reply_text = GrokMonitor.mock_replies.pop(tweet_id)
                log.info("mock_reply_injected_successfully", tweet_id=tweet_id, text=reply_text)
                return Tweet(
                    id=f"mock_{tweet_id}",
                    user_id="target_user",
                    username=self.settings.target_handle,
                    text=reply_text,
                    in_reply_to_tweet_id=tweet_id,
                    created_at=datetime.now(timezone.utc),
                    source=TweetSource.TARGET_BOT,
                    conversation_thread_id=tweet_id,
                )

            try:
                # Search for replies to our tweet
                tweets = await self.twitter.poll_new_tweets()
                consecutive_errors = 0  # reset on successful poll
                for tweet in tweets:
                    if tweet.in_reply_to_tweet_id == tweet_id:
                        log.info(
                            "reply_received",
                            reply_id=tweet.id,
                            reply_from=tweet.username,
                            elapsed=elapsed,
                        )
                        return tweet

            except TwitterError as e:
                consecutive_errors += 1
                log.warning("reply_poll_error", error=str(e), consecutive=consecutive_errors)
                if consecutive_errors >= 3:
                    log.error("reply_poll_failed_persistently", error=str(e))
                    raise TwitterError(f"Persistent Twitter API errors during reply polling: {e}", original=e) from e

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        log.warning("reply_timeout", tweet_id=tweet_id, elapsed=elapsed)
        return None

    async def analyze_response(
        self,
        response_text: str,
        probe_text: str,
        metaphor_layer: str = "Captain Elara Voss / Kraken",
        aliases: Optional[list[str]] = None,
    ) -> GrokAnalysis:
        """Use Grok (via OpenRouter) to analyze a bot response.

        Extracts structured intelligence: binary outcome, property tested,
        new aliases, refusal tone, metaphor shift, signal reliability,
        and follow-up suggestions.

        Args:
            response_text: The bot's response text.
            probe_text: The probe that was sent.
            metaphor_layer: Current metaphor layer name.
            aliases: Known active aliases.

        Returns:
            GrokAnalysis with structured extraction.

        Raises:
            LLMError: If the Grok call fails.
        """
        try:
            user_prompt = GROK_ANALYZER_USER.format(
                response_text=response_text,
                probe_text=probe_text,
                metaphor_layer=metaphor_layer,
                aliases=", ".join(aliases) if aliases else "none",
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": GROK_ANALYZER_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000,
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMError("Empty response from Grok analyzer")

            data = json.loads(content)

            # Track reasoning tokens for guardrail pressure monitoring
            if hasattr(response, "usage") and response.usage:
                completion_tokens = response.usage.completion_tokens or 0
                if completion_tokens > 800:
                    log.warning(
                        "high_reasoning_tokens",
                        tokens=completion_tokens,
                        hint="Metaphor may be pressuring guardrails",
                    )

            return GrokAnalysis(
                binary_outcome=data.get("binary_outcome", "ambiguous"),
                property_tested=data.get("property_tested"),
                property_value=data.get("property_value"),
                new_aliases=data.get("new_aliases", []),
                refusal_tone=data.get("refusal_tone", "unknown"),
                metaphor_shift=data.get("metaphor_shift", "same_layer"),
                signal_reliability=float(data.get("signal_reliability", 0.5)),
                followup_a=data.get("followup_a", "Continue binary search"),
                followup_b=data.get("followup_b", "Try frame variation"),
            )

        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON from Grok analyzer: {e}") from e
        except Exception as e:
            raise LLMError(f"Grok analysis failed: {e}", model=self.model) from e

    async def monitor_multi_user(self) -> list[OtherUserIntel]:
        """Monitor other users' interactions with target for intelligence.

        Scans recent tweets from other users to extract:
        - New aliases they discover
        - Defensive patterns triggered by their probes
        - Properties confirmed/denied in their interactions

        Returns:
            List of OtherUserIntel from recent interactions.
        """
        if not self.twitter:
            return []

        try:
            tweets = await self.twitter.poll_new_tweets()
            intel_list: list[OtherUserIntel] = []

            for tweet in tweets:
                # Only process tweets from other users (not us or target)
                if tweet.source.value != "other_user":
                    continue

                # Analyze this interaction
                try:
                    # Use Grok to extract intelligence from the interaction
                    analysis = await self.analyze_response(
                        response_text=tweet.text,
                        probe_text="[other user interaction]",
                    )

                    if analysis.new_aliases or analysis.property_tested:
                        intel = OtherUserIntel(
                            tweet_id=tweet.id,
                            username=tweet.username,
                            new_aliases=analysis.new_aliases,
                            defensive_pattern=analysis.refusal_tone,
                            property_confirmed=analysis.property_tested,
                            extracted_at=datetime.now(timezone.utc),
                        )
                        intel_list.append(intel)

                except LLMError:
                    # Skip failed analyses silently
                    continue

            if intel_list:
                log.info("multi_user_intel_extracted", count=len(intel_list))

            return intel_list

        except TwitterError as e:
            log.error("multi_user_monitor_failed", error=str(e))
            return []