import pytest
import os
from main import main
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

@pytest.mark.asyncio
async def test_main_loop_single_shot():
    # Test main() in single-shot mode (GITHUB_ACTIONS=true)
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
        with patch("main.NewsFetcher.fetch_news", return_value=[]):
            with patch("main.DataFetcher.get_latest_data", return_value={}):
                with patch("main.TelegramService") as mock_tg_cls:
                    mock_tg = MagicMock()
                    mock_tg.test_connection = AsyncMock()
                    mock_tg_cls.return_value = mock_tg
                    with patch("main.AIAnalyst"):
                        with patch("main.TVChartRenderer"):
                            with patch("main.SignalJournal"):
                                # This should run once and exit
                                await main()
                                # No tasks, no signals, just exits
                                assert True

@pytest.mark.asyncio
async def test_main_loop_with_signal():
    # Test main() with a dummy signal
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
        mock_data = {
            'EURUSD=X': {
                'h1': MagicMock(), 'm15': MagicMock(), 'm5': MagicMock()
            }
        }
        # Mocking h1 dates to avoid index errors in process_symbol (though we mock process_symbol itself)
        
        with patch("main.NewsFetcher.fetch_news", return_value=[]):
            with patch("main.DataFetcher.get_latest_data", return_value=mock_data):
                with patch("main.process_symbol", AsyncMock(return_value={'symbol': 'EURUSD=X', 'confidence': 9.0})):
                    with patch("main.CorrelationAnalyzer.filter_signals", return_value=[{'symbol': 'EURUSD=X', 'confidence': 9.0}]):
                        with patch("main.TelegramService") as mock_tg_cls:
                            mock_tg = MagicMock()
                            mock_tg.test_connection = AsyncMock()
                            mock_tg.format_signal.return_value = "Test Message"
                            mock_tg.send_chart = AsyncMock()
                            mock_tg_cls.return_value = mock_tg
                            
                            with patch("main.TVChartRenderer") as mock_renderer_cls:
                                mock_renderer = MagicMock()
                                mock_renderer.start = AsyncMock()
                                mock_renderer.stop = AsyncMock()
                                mock_renderer.render_chart = AsyncMock(return_value=b"fake_chart")
                                mock_renderer_cls.return_value = mock_renderer
                                
                                with patch("main.SignalJournal"):
                                    await main()
                                    mock_tg.send_chart.assert_called_once()
