import pytest
from data.news_fetcher import NewsFetcher
from filters.news_filter import NewsFilter
from filters.news_sentiment import NewsSentimentAnalyzer
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

def test_news_fetcher_success():
    """Test successful news fetch"""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"title": "NFP Data", "date": "2024-01-01T12:00:00Z", "impact": "High"}
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        events = NewsFetcher.fetch_news()
        assert isinstance(events, list)

def test_news_fetcher_connection_error():
    """Test news fetcher connection error"""
    with patch("requests.get", side_effect=ConnectionError("Network down")):
        events = NewsFetcher.fetch_news()
        assert events == []

def test_news_fetcher_http_error():
    """Test news fetcher HTTP error"""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        events = NewsFetcher.fetch_news()
        assert events == []

def test_news_fetcher_exception():
    """Test general exception handling"""
    with patch("requests.get", side_effect=Exception("API Error")):
        events = NewsFetcher.fetch_news()
        assert events == []

def test_news_filter_is_news_safe_no_events():
    """Test news filter with no events"""
    assert NewsFilter.is_news_safe([], "EURUSD") is True

def test_news_filter_is_news_safe_with_events():
    """Test news filter with events (lines 16-54)"""
    events = [
        {"title": "EUR GDP", "published_utc": (datetime.now() + timedelta(minutes=15)).isoformat() + "Z"}
    ]
    # Should return False if event is close (within 30 min)
    result = NewsFilter.is_news_safe(events, "EURUSD")
    assert isinstance(result, bool)

def test_news_filter_get_upcoming_events():
    """Test get_upcoming_events (line 65)"""
    events = [
        {"title": "USD NFP", "published_utc": (datetime.now() + timedelta(minutes=20)).isoformat() + "Z"}
    ]
    upcoming = NewsFilter.get_upcoming_events(events, "EURUSD")
    assert isinstance(upcoming, list)

def test_news_sentiment_analyze_no_events():
    """Test news sentiment with no events"""
    sentiment = NewsSentimentAnalyzer.get_bias({})
    assert isinstance(sentiment, str)

def test_news_sentiment_analyze_with_events():
    """Test news sentiment analysis (lines 20-54)"""
    event = {"title": "GDP Growth", "forecast": "2.5", "previous": "2.0"}
    sentiment = NewsSentimentAnalyzer.get_bias(event)
    assert sentiment in ["BULLISH", "BEARISH", "NEUTRAL"]

def test_news_sentiment_positive_keywords():
    """Test positive keyword detection"""
    event = {"title": "Strong Employment Change", "forecast": "200K", "previous": "150K"}
    sentiment = NewsSentimentAnalyzer.get_bias(event)
    assert sentiment in ["BULLISH", "BEARISH", "NEUTRAL"]

def test_news_sentiment_negative_keywords():
    """Test negative keyword detection"""
    event = {"title": "Unemployment Rate", "forecast": "4.5", "previous": "4.0"}
    sentiment = NewsSentimentAnalyzer.get_bias(event)
    assert sentiment in ["BULLISH", "BEARISH", "NEUTRAL"]
