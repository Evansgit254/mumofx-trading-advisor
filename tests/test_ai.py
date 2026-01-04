import pytest
from ai.analyst import AIAnalyst

@pytest.mark.asyncio
async def test_ai_validation_no_key():
    # Test behavior when API key is missing
    analyst = AIAnalyst() # GEMINI_API_KEY is None in test env if not set
    data = {
        'pair': 'EURUSD',
        'direction': 'BUY',
        'h1_trend': 'BULLISH',
        'setup_tf': 'M15_SWEEP',
        'liquidity_event': 'Sweep of M15 Low',
        'confidence': 9.2
    }
    result = await analyst.validate_signal(data)
    assert result['valid'] is True
    assert "skipped" in result['reason'].lower()

@pytest.mark.asyncio
async def test_ai_sentiment_no_key():
    analyst = AIAnalyst()
    sentiment = await analyst.get_market_sentiment([], "EURUSD")
    assert "Neutral" in sentiment
