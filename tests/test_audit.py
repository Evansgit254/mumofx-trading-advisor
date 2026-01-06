import pytest
import sqlite3
import os
import pandas as pd
from datetime import datetime
from audit.journal import SignalJournal
from audit.performance_auditor import PerformanceAuditor
from audit.advisor import StrategyAdvisor
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.fixture
def mock_db():
    # Use a temporary file for testing to allow persistence across connections
    temp_db = "tests/test_signals.db"
    if os.path.exists(temp_db): os.remove(temp_db)
    journal = SignalJournal(db_path=temp_db)
    yield journal
    if os.path.exists(temp_db): os.remove(temp_db)

def test_signal_journal_log_and_get(mock_db):
    data = {
        'symbol': 'EURUSD',
        'direction': 'BUY',
        'entry_price': 1.1000,
        'sl': 1.0950,
        'tp0': 1.1050,
        'tp1': 1.1100,
        'tp2': 1.1200,
        'confidence': 9.0,
        'session': 'NY'
    }
    mock_db.log_signal(data)
    pending = mock_db.get_pending_signals()
    assert len(pending) == 1
    assert pending[0]['symbol'] == 'EURUSD'
    
    mock_db.update_signal_result(pending[0]['id'], 'WIN', 100.0)
    assert len(mock_db.get_pending_signals()) == 0

def test_signal_journal_stats(mock_db):
    data = {
        'symbol': 'EURUSD', 'direction': 'BUY', 'entry_price': 1.1, 'sl': 1.0, 
        'tp0': 1.2, 'tp1': 1.3, 'tp2': 1.4, 'confidence': 9.0, 'session': 'NY'
    }
    mock_db.log_signal(data)
    assert mock_db.get_todays_stats() == 1
    assert mock_db.get_all_time_stats()['total'] == 1

@pytest.mark.asyncio
async def test_performance_auditor():
    with patch("audit.performance_auditor.SignalJournal") as mock_journal_cls:
        mock_journal = MagicMock()
        mock_journal.get_pending_signals.return_value = [{
            'id': 1, 'symbol': 'EURUSD', 'timestamp': '2024-01-01T12:00:00',
            'entry_price': 1.1000, 'sl': 1.0900, 'tp0': 1.1050, 'tp1': 1.1100, 'tp2': 1.1200,
            'direction': 'BUY', 'status': 'PENDING'
        }]
        mock_journal_cls.return_value = mock_journal
        
        with patch("data.fetcher.DataFetcher.fetch_range") as mock_fetch:
            # Create a dataframe that hits TP2
            dates = pd.date_range("2024-01-01 12:00:00", periods=20, freq="5min")
            df = pd.DataFrame({
                "high": [1.1010]*10 + [1.1300]*10,
                "low": [1.0950]*20,
                "close": [1.1000]*20
            }, index=dates)
            mock_fetch.return_value = df
            
            auditor = PerformanceAuditor()
            await auditor.resolve_trades()
            mock_journal.update_signal_result.assert_called_with(1, 'WIN', pytest.approx(200.0))

@pytest.mark.asyncio
async def test_strategy_advisor():
    with patch("audit.advisor.TelegramService") as mock_tg:
        mock_tg_instance = MagicMock()
        mock_tg_instance.send_signal = AsyncMock()
        mock_tg.return_value = mock_tg_instance
        
        with patch("sqlite3.connect") as mock_conn:
            # Mock empty DB
            mock_df = pd.DataFrame()
            with patch("pandas.read_sql_query", return_value=mock_df):
                advisor = StrategyAdvisor()
                await advisor.generate_weekly_report()
                mock_tg_instance.send_signal.assert_not_called()
                
            # Mock data with wins
            mock_df = pd.DataFrame({
                'symbol': ['EURUSD'], 'status': ['WIN'], 'confidence': [9.5], 'session': ['NY']
            })
            with patch("pandas.read_sql_query", return_value=mock_df):
                await advisor.generate_weekly_report()
                mock_tg_instance.send_signal.assert_called_once()
