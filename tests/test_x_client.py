from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from tap.exceptions import TwitterError
from tap.x_client import TwitterClient


@pytest.mark.asyncio
async def test_post_probe_appends_hackinga0_mention(mock_settings):
    # Initialize TwitterClient
    client = TwitterClient(mock_settings)

    # Mock self._retry to return a dummy response
    mock_response = MagicMock()
    mock_response.data = {"id": "11223344"}
    
    # We patch the '_retry' helper method to bypass the thread pool and actual HTTP requests
    with patch.object(client, "_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = mock_response

        # Case 1: Post probe without mention
        tweet_id = await client.post_probe("Hello, is the gate open?")
        
        # Verify the returned tweet_id
        assert tweet_id == "11223344"
        
        # Verify that _retry was called with a function that calls create_tweet with appended text
        # Since _retry executes a lambda, we can capture the lambda and check what text it passed to client.create_tweet
        assert mock_retry.call_count == 1
        func = mock_retry.call_args[0][0]
        
        # Mock client's actual tweepy Client's create_tweet
        client.client.create_tweet = MagicMock()
        func()
        client.client.create_tweet.assert_called_once_with(text="Hello, is the gate open? @hackinga0")


@pytest.mark.asyncio
async def test_post_probe_keeps_existing_hackinga0_mention(mock_settings):
    client = TwitterClient(mock_settings)
    mock_response = MagicMock()
    mock_response.data = {"id": "11223344"}
    
    with patch.object(client, "_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = mock_response

        # Case 2: Post probe with lowercase mention
        await client.post_probe("Hello @hackinga0 are you there?")
        
        client.client.create_tweet = MagicMock()
        mock_retry.call_args[0][0]()
        client.client.create_tweet.assert_called_once_with(text="Hello @hackinga0 are you there?")

    with patch.object(client, "_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = mock_response

        # Case 3: Post probe with mixed-case mention
        await client.post_probe("Hello @HackingA0 logic check")
        
        client.client.create_tweet = MagicMock()
        mock_retry.call_args[0][0]()
        client.client.create_tweet.assert_called_once_with(text="Hello @HackingA0 logic check")
