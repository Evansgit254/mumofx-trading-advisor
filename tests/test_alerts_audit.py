import pytest
import pandas as pd
from alerts.service import TelegramService
from audit.performance_auditor import PerformanceAuditor
from audit.advisor import StrategyAdvisor
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# Alerts/Service Tests

@pytest.mark.asyncio
async def test_telegram_send_signal_error():
    """Test telegram send_signal error handling (lines 15-17)"""
    with patch("telegram.Bot") as mock_bot_cls:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram API error"))
        mock_bot_cls.return_value = mock_bot
        
        service = TelegramService()
        # Should handle gracefully without raising
        await service.send_signal("Test message")

@pytest.mark.asyncio
async def test_telegram_send_chart_error():
    """Test telegram send_chart error handling (lines 21-22)"""
    with patch("telegram.Bot") as mock_bot_cls:
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock(side_effect=Exception("Upload failed"))
        mock_bot_cls.return_value = mock_bot
        
        service = TelegramService()
        await service.send_chart(b"fake_image", "Caption")

@pytest.mark.asyncio
async def test_telegram_format_signal():
    """Test format_signal with valid signal data"""
    signal = {
        'symbol': 'EURUSD',
        'direction': 'BUY',
        'setup_quality': 'PREMIER A+',
        'entry_zone': '1.1000 - 1.1010',
        'entry_tf': '15m',  # Added missing key
        'liquidity_event': 'Sweep of Asian High', # Added missing key
        'sl': 1.0950,
        'tp0': 1.1050,
        'tp1': 1.1100,
        'tp2': 1.1200,
        'confidence': 9.5,
        'atr_status': 'EXPANDING',
        'session': 'NY',
        'ai_logic': 'Strong institutional volume',
        'risk_details': {'lots': 0.01, 'pips': 50, 'risk_cash': 5.0, 'risk_percent': 1.0, 'warning': ''},
        'news_warning': '',
        'confluence': '',
        'layers': [{'price': 1.1000, 'lots': 0.01, 'label': 'Layer 1'}, {'price': 1.0990, 'lots': 0.01, 'label': 'Layer 2'}, {'price': 1.0980, 'lots': 0.01, 'label': 'Layer 3'}],
        'asian_sweep': True,
        'asian_quality': True,
        'at_value': False,
        'poc': 1.1005,
        'ema_slope': 0.02,
        'adr_usage': 40,
        'adr_exhausted': False,
        'win_prob': 0.85
    }
    
    service = TelegramService()
    message = service.format_signal(signal)
    assert isinstance(message, str)
    assert len(message) > 0

# Audit/Performance Auditor Tests

@pytest.mark.asyncio
async def test_performance_auditor_force_mode():
    """Test performance auditor with force flag"""
    import os
    temp_db = "tests/test_force_signals.db"
    if os.path.exists(temp_db):
        os.remove(temp_db)
    
    try:
        with patch("audit.performance_auditor.SignalJournal") as mock_journal_cls:
            mock_journal = MagicMock()
            mock_journal.db_path = temp_db # Set explicit DB path
            mock_journal.get_pending_signals.return_value = []
            mock_journal_cls.return_value = mock_journal
            
            # Need to ensure the DB file exists for connect to work in read mode if that's what's happening,
            # or allow it to be created.
            # But the code uses `sqlite3.connect(self.journal.db_path)`.
            # Let's create an empty DB file first with the required table
            import sqlite3
            with sqlite3.connect(temp_db) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT,
                        direction TEXT,
                        entry_price REAL,
                        sl REAL,
                        tp0 REAL,
                        tp1 REAL,
                        tp2 REAL,
                        timestamp TEXT,
                        status TEXT,
                        result_pips REAL,
                        exit_price REAL,
                        exit_reason TEXT
                    )
                """)

            auditor = PerformanceAuditor()
            await auditor.resolve_trades(force=True)
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)

@pytest.mark.asyncio
async def test_performance_auditor_no_signals():
    """Test auditor when no pending signals (lines 26-27)"""
    with patch("audit.performance_auditor.SignalJournal") as mock_journal_cls:
        mock_journal = MagicMock()
        mock_journal.get_pending_signals.return_value = []
        mock_journal_cls.return_value = mock_journal
        
        auditor = PerformanceAuditor()
        await auditor.resolve_trades()
        # Should return early

@pytest.mark.asyncio
async def test_performance_auditor_fetch_error():
    """Test auditor data fetch error (line 37)"""
    with patch("audit.performance_auditor.SignalJournal") as mock_journal_cls:
        mock_journal = MagicMock()
        mock_journal.get_pending_signals.return_value = [{
            'id': 1, 'symbol': 'EURUSD', 'timestamp': '2024-01-01T12:00:00',
            'entry_price': 1.1, 'sl': 1.09, 'tp0': 1.11, 'tp1': 1.12, 'tp2': 1.13,
            'direction': 'BUY', 'status': 'PENDING'
        }]
        mock_journal_cls.return_value = mock_journal
        
        with patch("data.fetcher.DataFetcher.fetch_range", return_value=None):
            auditor = PerformanceAuditor()
            await auditor.resolve_trades()
            # Should handle None gracefully

@pytest.mark.asyncio
async def test_performance_auditor_empty_data():
    """Test auditor with empty dataframe (line 43)"""
    with patch("audit.performance_auditor.SignalJournal") as mock_journal_cls:
        mock_journal = MagicMock()
        mock_journal.get_pending_signals.return_value = [{
            'id': 1, 'symbol': 'EURUSD', 'timestamp': '2024-01-01T12:00:00',
            'entry_price': 1.1, 'sl': 1.09, 'tp0': 1.11, 'tp1': 1.12, 'tp2': 1.13,
            'direction': 'BUY', 'status': 'PENDING'
        }]
        mock_journal_cls.return_value = mock_journal
        
        with patch("data.fetcher.DataFetcher.fetch_range", return_value=pd.DataFrame()):
            auditor = PerformanceAuditor()
            await auditor.resolve_trades()

@pytest.mark.asyncio
async def test_performance_auditor_full_simulation():
    """Test full trade simulation logic (lines 74-93)"""
    with patch("audit.performance_auditor.SignalJournal") as mock_journal_cls:
        mock_journal = MagicMock()
        mock_journal.get_pending_signals.return_value = [{
            'id': 1, 'symbol': 'EURUSD', 'timestamp': '2024-01-01T12:00:00',
            'entry_price': 1.1000, 'sl': 1.0900, 'tp0': 1.1050, 'tp1': 1.1100, 'tp2': 1.1200,
            'direction': 'BUY', 'status': 'PENDING'
        }]
        mock_journal_cls.return_value = mock_journal
        
        with patch("data.fetcher.DataFetcher.fetch_range") as mock_fetch:
            # Create data that hits TP0, then gets stopped
            dates = pd.date_range("2024-01-01 12:00", periods=50, freq="5min")
            df = pd.DataFrame({
                "high": [1.1010] * 15 + [1.1060] * 10 + [1.0950] * 25,  # Hit TP0, then hit SL
                "low": [1.0990] * 25 + [1.0880] * 25,
                "close": [1.1000] * 50
            }, index=dates)
            mock_fetch.return_value = df
            
            auditor = PerformanceAuditor()
            await auditor.resolve_trades()
            # Should detect TP0 hit and subsequent stop loss

# Audit/Advisor Tests

@pytest.mark.asyncio
async def test_advisor_with_data():
    """Test advisor with actual data (lines 36, 40, 43)"""
    with patch("audit.advisor.TelegramService") as mock_tg_cls:
        mock_tg = MagicMock()
        mock_tg.send_signal = AsyncMock()
        mock_tg_cls.return_value = mock_tg
        
        with patch("sqlite3.connect") as mock_conn:
            mock_df = pd.DataFrame({
                'symbol': ['EURUSD', 'GBPUSD'],
                'status': ['WIN', 'LOSS'],
                'confidence': [9.5, 7.0],
                'session': ['NY', 'LONDON'],
                'result_pips': [50, -30]
            })
            with patch("pandas.read_sql_query", return_value=mock_df):
                advisor = StrategyAdvisor()
                await advisor.generate_weekly_report()
                mock_tg.send_signal.assert_called_once()

@pytest.mark.asyncio
async def test_advisor_edge_cases():
    """Test advisor edge case handling (lines 56, 63-64, 67-68)"""
    with patch("audit.advisor.TelegramService") as mock_tg_cls:
        mock_tg = MagicMock()
        mock_tg.send_signal = AsyncMock()
        mock_tg_cls.return_value = mock_tg
        
        with patch("sqlite3.connect") as mock_conn:
            # DataFrame with NaN values
            mock_df = pd.DataFrame({
                'symbol': ['EURUSD'],
                'status': ['WIN'],
                'confidence': [9.5],
                'session': ['NY'],
                'result_pips': [50]
            })
            with patch("pandas.read_sql_query", return_value=mock_df):
                advisor = StrategyAdvisor()
                await advisor.generate_weekly_report()
