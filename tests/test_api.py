import pytest
from fastapi.testclient import TestClient
from tap.api import app
import tap.api as api
from unittest.mock import AsyncMock, MagicMock

def test_force_fetch_replies_success():
    # Mock Database
    mock_db = MagicMock()
    mock_db.upsert_tweet = AsyncMock()
    
    # Mock Twitter client
    mock_tweet = MagicMock()
    mock_tweet.id = "12345"
    
    mock_twitter = MagicMock()
    mock_twitter.initialize_seed = AsyncMock(return_value=[mock_tweet])
    
    # Mock Engine
    mock_engine = MagicMock()
    mock_engine.twitter = mock_twitter
    
    # Inject mocks
    api._db = mock_db
    api._engine = mock_engine
    
    client = TestClient(app)
    response = client.post("/api/fetch")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["count"] == 1
    
    mock_twitter.initialize_seed.assert_called_once_with(limit=50)
    mock_db.upsert_tweet.assert_called_once_with(mock_tweet)
    
    # Reset
    api._db = None
    api._engine = None

def test_force_fetch_replies_not_initialized():
    # Clear globals to test uninitialized case
    api._db = None
    api._engine = None
    
    client = TestClient(app)
    response = client.post("/api/fetch")
    
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"] == "Engine or Database not initialized"

def test_force_fetch_replies_exception_handling():
    # Setup mock raising exception
    mock_db = MagicMock()
    mock_twitter = MagicMock()
    mock_twitter.initialize_seed = AsyncMock(side_effect=Exception("Twitter API Offline"))
    
    mock_engine = MagicMock()
    mock_engine.twitter = mock_twitter
    
    api._db = mock_db
    api._engine = mock_engine
    
    client = TestClient(app)
    response = client.post("/api/fetch")
    
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "Twitter API Offline" in data["error"]
    
    api._db = None
    api._engine = None
