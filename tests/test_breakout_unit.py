import pytest
import pandas as pd
import numpy as np
from strategies.breakout_strategy import BreakoutStrategy
from unittest.mock import patch, AsyncMock, MagicMock

@pytest.fixture
def strategy():
    return BreakoutStrategy()

@pytest.fixture
def mock_data():
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=100, freq="5min")
    df = pd.DataFrame({
        'open': np.linspace(1.10, 1.11, 100),
        'high': np.linspace(1.11, 1.12, 100),
        'low': np.linspace(1.09, 1.10, 100),
        'close': np.linspace(1.105, 1.115, 100),
        'volume': [1000] * 100,
        'atr': [0.001] * 100,
        'rsi': [55] * 100
    }, index=dates)
    df['regime'] = "TRENDING"
    df['asian_high'] = 1.11
    df['asian_low'] = 1.10
    df['atr_ma_20'] = 0.001
    df['fvg_bullish'] = False
    df['fvg_bearish'] = False
    df['bos_buy'] = False
    df['bos_sell'] = False
    
    # M15 context
    m15_dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=100, freq="15min")
    m15_df = df.copy().set_index(m15_dates)
    
    return {'m5': df, 'm15': m15_df}

def test_breakout_metadata(strategy):
    assert strategy.get_id() == "breakout_master"
    assert strategy.get_name() == "Breakout Master"

@pytest.mark.asyncio
async def test_breakout_regime_filtering(strategy, mock_data):
    # Test regime != TRENDING
    mock_data['m15']['regime'] = "RANGING"
    res = await strategy.analyze("EURUSD=X", mock_data, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_breakout_buy_logic(strategy, mock_data):
    # Setup TRENDING regime
    mock_data['m15']['regime'] = "TRENDING"
    mock_data['m15']['asian_high'] = 1.11
    mock_data['m15']['asian_low'] = 1.10
    
    # Setup latest close above high, prev below
    mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('close')] = 1.115
    mock_data['m5'].iloc[-2, mock_data['m5'].columns.get_loc('close')] = 1.105
    
    with patch("filters.macro_filter.MacroFilter.get_macro_bias", return_value="BULLISH"):
        with patch("filters.macro_filter.MacroFilter.is_macro_safe", return_value=True):
            with patch("filters.session_filter.SessionFilter.is_valid_session", return_value=True):
                # Mock AI Score - V15.0 Hardened Threshold (8.0)
                strategy.ai_grader.get_score = AsyncMock(return_value=8.5)
                
                res = await strategy.analyze("EURUSD=X", mock_data, [], {})
                
                assert res is not None
                assert res['direction'] == "BUY"
                assert res['confidence'] >= 8.0
                assert res['setup_quality'] == "BREAKOUT"

@pytest.mark.asyncio
async def test_breakout_sell_logic(strategy, mock_data):
    # Setup TRENDING regime
    mock_data['m15']['regime'] = "TRENDING"
    mock_data['m15']['asian_high'] = 1.11
    mock_data['m15']['asian_low'] = 1.10
    
    # Setup latest close below low, prev above
    mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('close')] = 1.095
    mock_data['m5'].iloc[-2, mock_data['m5'].columns.get_loc('close')] = 1.105
    mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('rsi')] = 40
    
    with patch("filters.macro_filter.MacroFilter.get_macro_bias", return_value="BEARISH"):
        with patch("filters.macro_filter.MacroFilter.is_macro_safe", return_value=True):
            with patch("filters.session_filter.SessionFilter.is_valid_session", return_value=True):
                # Mock AI Score - V15.0 Hardened Threshold (8.0)
                strategy.ai_grader.get_score = AsyncMock(return_value=9.0)
                
                res = await strategy.analyze("EURUSD=X", mock_data, [], {})
                
                assert res is not None
                assert res['direction'] == "SELL"
                assert res['confidence'] >= 8.0

@pytest.mark.asyncio
async def test_breakout_ai_rejection(strategy, mock_data):
    mock_data['m15']['regime'] = "TRENDING"
    mock_data['m15']['asian_high'] = 1.11
    mock_data['m15']['asian_low'] = 1.10
    
    mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('close')] = 1.115
    mock_data['m5'].iloc[-2, mock_data['m5'].columns.get_loc('close')] = 1.105
    
    with patch("filters.macro_filter.MacroFilter.is_macro_safe", return_value=True):
        with patch("filters.session_filter.SessionFilter.is_valid_session", return_value=True):
            # Mock Low AI Score
            strategy.ai_grader.get_score = AsyncMock(return_value=6.0)
            
            res = await strategy.analyze("EURUSD=X", mock_data, [], {})
            assert res is None
