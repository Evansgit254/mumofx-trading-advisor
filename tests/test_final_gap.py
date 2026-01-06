import pytest
import pandas as pd
from alerts.service import TelegramService
from data.news_fetcher import NewsFetcher
from filters.news_filter import NewsFilter
from unittest.mock import MagicMock, AsyncMock, patch

# Alerts: Gold Emoji Coverage
@pytest.mark.asyncio
async def test_telegram_gold_emoji():
    signal = {
        'symbol': 'GC=F',  # Gold
        'direction': 'BUY',
        'setup_quality': 'A',
        'entry_zone': '2000-2001',
        'entry_tf': '15m',
        'liquidity_event': 'Sweep',
        'sl': 1995, 'tp0': 2005, 'tp1': 2010, 'tp2': 2020,
        'confidence': 9.0, 'atr_status': 'NORMAL', 'session': 'NY',
        'ai_logic': 'Logic', 'risk_details': {'lots': 1, 'pips': 10, 'risk_cash': 10, 'risk_percent': 1, 'warning': ''},
        'news_warning': '', 'confluence': '', 
        'layers': [{'price': 2000, 'lots': 0.3, 'label': 'L1'}, {'price': 1999, 'lots': 0.3, 'label': 'L2'}, {'price': 1998, 'lots': 0.4, 'label': 'L3'}],
        'win_prob': 0.88, 'adr_usage': 50, 'adr_exhausted': False, 'at_value': False, 'poc': 2000, 'ema_slope': 0.1, 'asian_sweep': False, 'asian_quality': False
    }
    service = TelegramService()
    msg = service.format_signal(signal)
    assert "🚀" in msg  # Gold Buy Emoji

    signal['direction'] = 'SELL'
    msg = service.format_signal(signal)
    assert "☄️" in msg  # Gold Sell Emoji

# News Fetcher: Filter Logic Coverage
def test_filter_relevant_news():
    events = [
        {"country": "USD", "title": "NFP"},
        {"country": "EUR", "title": "GDP"},
        {"country": "JPY", "title": "Rate"},
        {"country": "CAD", "title": "CPI"}
    ]
    # Filter for EURUSD (EUR, USD)
    filtered = NewsFetcher.filter_relevant_news(events, ["EURUSD=X"])
    assert len(filtered) == 2
    countries = [e['country'] for e in filtered]
    assert "USD" in countries
    assert "EUR" in countries

# News Filter: Event Parsing Loop Coverage
def test_news_filter_loop():
    # Create events that match and don't match criteria
    events = [
        # Match: USD High Impact
        {"country": "USD", "impact": "High", "date": "2026-01-01T12:00:00-05:00", "title": "NFP"},
        # Skip: Low Impact
        {"country": "USD", "impact": "Low", "date": "2026-01-01T12:00:00-05:00", "title": "Talk"},
        # Skip: Wrong Currency
        {"country": "JPY", "impact": "High", "date": "2026-01-01T12:00:00-05:00", "title": "Rate"},
    ]
    
    with patch("filters.news_filter.datetime") as mock_dt:
        # Mock current time to be close to event
        mock_now = pd.Timestamp("2026-01-01T11:45:00-05:00")
        mock_dt.now.return_value = mock_now
        
        upcoming = NewsFilter.get_upcoming_events(events, "EURUSD=X")
        assert len(upcoming) == 1
        assert upcoming[0]['title'] == "NFP"
