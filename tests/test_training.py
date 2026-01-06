import pytest
import pandas as pd
import numpy as np
import os
import joblib
from training.trainer import train_model
from training.data_collector import collect_training_data
from training.optimizer import run_optimization
from unittest.mock import MagicMock, patch, AsyncMock

def create_realistic_sweep_data(num_bars=300):
    """Create realistic OHLCV data with actual sweep patterns"""
    np.random.seed(42)
    
    # Create base price movement with trend
    base_price = 1.1000
    trend = np.linspace(0, 0.02, num_bars)  # Uptrend
    noise = np.random.normal(0, 0.001, num_bars)
    close_prices = base_price + trend + noise
    
    # Create OHLC from close
    high_prices = close_prices + np.abs(np.random.normal(0, 0.0005, num_bars))
    low_prices = close_prices - np.abs(np.random.normal(0, 0.0005, num_bars))
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = close_prices[0]
    
    # Add volume
    volume = np.random.uniform(1000, 10000, num_bars)
    
    # Create sweep pattern: bar 150 sweeps below previous lows then closes above
    lookback_low = low_prices[130:150].min()
    low_prices[150] = lookback_low - 0.0010  # Sweep below
    close_prices[150] = lookback_low + 0.0005  # Close back above
    high_prices[150] = max(high_prices[150], close_prices[150])
    
    return pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volume
    })

@pytest.fixture
def mock_training_data():
    df = pd.DataFrame({
        'rsi': [50, 60, 40] * 20,
        'body_ratio': [0.5, 0.6, 0.4] * 20,
        'atr_norm': [0.01, 0.02, 0.015] * 20,
        'displaced': [1, 0, 1] * 20,
        'h1_trend': [1, -1, 1] * 20,
        'outcome': [1, 0, 1] * 20
    })
    return df

def test_trainer_with_data(mock_training_data):
    """Test trainer with valid dataset"""
    with patch("pandas.read_csv", return_value=mock_training_data):
        with patch("os.path.exists", return_value=True):
            with patch("joblib.dump") as mock_save:
                with patch("sqlite3.connect") as mock_conn:
                    with patch("pandas.read_sql_query", return_value=pd.DataFrame()):
                        train_model()
                        mock_save.assert_called()

def test_trainer_no_data():
    """Test trainer when CSV doesn't exist"""
    with patch("os.path.exists", return_value=False):
        train_model()
        # Should print error and return early

def test_trainer_small_dataset():
    """Test trainer with dataset < 50 samples (triggers warning)"""
    small_df = pd.DataFrame({
        'rsi': [50] * 30,
        'body_ratio': [0.5] * 30,
        'atr_norm': [0.01] * 30,
        'displaced': [1] * 30,
        'h1_trend': [1] * 30,
        'outcome': [1] * 30
    })
    with patch("pandas.read_csv", return_value=small_df):
        with patch("os.path.exists", return_value=True):
            with patch("joblib.dump"):
                with patch("sqlite3.connect"):
                    with patch("pandas.read_sql_query", return_value=pd.DataFrame()):
                        train_model()
                        # Should trigger warning about small dataset

def test_trainer_with_live_signals():
    """Test trainer integration with live signals database"""
    mock_training_data = pd.DataFrame({
        'rsi': [50] * 60,
        'body_ratio': [0.5] * 60,
        'atr_norm': [0.01] * 60,
        'displaced': [1] * 60,
        'h1_trend': [1] * 60,
        'outcome': [1] * 60
    })
    
    live_signals = pd.DataFrame({
        'symbol': ['EURUSD', 'GBPUSD'],
        'result_pips': [50, -30],
        'status': ['WIN', 'LOSS']
    })
    
    with patch("pandas.read_csv", return_value=mock_training_data):
        with patch("os.path.exists", return_value=True):
            with patch("joblib.dump"):
                with patch("sqlite3.connect"):
                    with patch("pandas.read_sql_query", return_value=live_signals):
                        train_model()
                        # Should integrate live signals

@pytest.mark.asyncio
async def test_data_collector_with_sweeps():
    """Test data collector with realistic sweep patterns"""
    with patch("data.fetcher.DataFetcher.fetch_range") as mock_fetch:
        # Create realistic data with sweep patterns
        h1_data = create_realistic_sweep_data(300)
        m15_data = create_realistic_sweep_data(500)
        m5_data = create_realistic_sweep_data(1000)
        
        # Add required dates as index
        h1_data.index = pd.date_range("2024-01-01", periods=len(h1_data), freq="1h", tz="UTC")
        m15_data.index = pd.date_range("2024-01-01", periods=len(m15_data), freq="15min", tz="UTC")
        m5_data.index = pd.date_range("2024-01-01", periods=len(m5_data), freq="5min", tz="UTC")
        
        mock_fetch.side_effect = lambda symbol, tf, start, end: {
            "1h": h1_data,
            "15m": m15_data,
            "5m": m5_data
        }.get(tf)
        
        with patch("pandas.DataFrame.to_csv") as mock_csv:
            await collect_training_data(days=1)
            # Should find setups and save data
            assert mock_csv.called

@pytest.mark.asyncio
async def test_data_collector_no_setups():
    """Test data collector when no setups are found (empty/None DataFrames)"""
    with patch("data.fetcher.DataFetcher.fetch_range", return_value=None):
        with patch("pandas.DataFrame.to_csv") as mock_csv:
            await collect_training_data(days=1)
            # Should handle gracefully and save empty/minimal data

@pytest.mark.asyncio
async def test_optimizer_full_loop():
    """Test optimizer with both BUY and SELL scenarios"""
    with patch("data.fetcher.DataFetcher.fetch_range") as mock_fetch:
        # Create bullish trend data for BUY scenarios
        bullish_data = create_realistic_sweep_data(200)
        bullish_data.index = pd.date_range("2024-01-01", periods=len(bullish_data), freq="15min", tz="UTC")
        bullish_data['atr'] = 0.001
        
        # Create separate bearish data for SELL scenarios  
        bearish_data = bullish_data.copy()
        bearish_data['close'] = bearish_data['close'][::-1].values  # Reverse for downtrend
        bearish_data['high'] = bearish_data['high'][::-1].values
        bearish_data['low'] = bearish_data['low'][::-1].values
        
        call_count = [0]
        def mock_fetch_side_effect(symbol, tf, start, end):
            call_count[0] += 1
            # Alternate between bullish and bearish to trigger both paths
            if call_count[0] % 6 <= 2:  # H1, M15, M5 for first symbol
                return bullish_data if tf != "1h" else bullish_data.resample("1h").agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
                })
            else:
                return bearish_data if tf != "1h" else bearish_data.resample("1h").agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
                })
        
        mock_fetch.side_effect = mock_fetch_side_effect
        
        with patch("pandas.DataFrame.to_csv") as mock_csv:
            await run_optimization()
            assert mock_csv.called
            # Both BUY and SELL branches should execute
