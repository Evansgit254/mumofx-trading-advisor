import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from ai.analyst import AIAnalyst
from alerts.service import TelegramService
from data.fetcher import DataFetcher
import pandas as pd
import io

@pytest.mark.asyncio
async def test_ai_analyst_success():
    with patch("google.genai.Client") as mock_client_class:
        # Configure mock
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"valid": true, "institutional_logic": "Test logic", "score_adjustment": 0.5}'
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_instance
        
        with patch("config.config.GEMINI_API_KEY", "test_key"):
            analyst = AIAnalyst()
            res = await analyst.validate_signal({"pair": "EURUSD", "direction": "BUY", "h1_trend": "BULL", "setup_tf": "M5", "liquidity_event": "Sweep", "confidence": 1.0})
            assert res["valid"] is True
            assert res["score_adjustment"] == 0.5

@pytest.mark.asyncio
async def test_telegram_service():
    with patch("telegram.Bot") as mock_bot:
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_message = AsyncMock()
        mock_bot.return_value = mock_bot_instance
        
        with patch("config.config.TELEGRAM_BOT_TOKEN", "test_token"):
            service = TelegramService()
            await service.send_signal("Test Message")
            mock_bot_instance.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_telegram_send_chart():
    with patch("telegram.Bot") as mock_bot:
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_photo = AsyncMock()
        mock_bot.return_value = mock_bot_instance
        
        service = TelegramService()
        dummy_photo = io.BytesIO(b"dummy_data")
        await service.send_chart(dummy_photo, "Test Caption")
        mock_bot_instance.send_photo.assert_called_once()

def test_data_fetcher_range():
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_df = pd.DataFrame({
            "Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.0], "Volume": [100]
        }, index=[pd.Timestamp.now(tz="UTC")])
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance
        
        res = DataFetcher.fetch_range("EURUSD=X", "1h", "2024-01-01", "2024-01-02")
        assert not res.empty
        assert "close" in res.columns
