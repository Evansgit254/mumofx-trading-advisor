import pytest
import pandas as pd
import numpy as np
from strategies.price_action_strategy import PriceActionStrategy
from unittest.mock import patch, AsyncMock, MagicMock

@pytest.fixture
def strategy():
    return PriceActionStrategy()

@pytest.fixture
def mock_data():
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=100, freq="5min")
    df = pd.DataFrame({
        'open': [1.10] * 100,
        'high': [1.11] * 100,
        'low': [1.09] * 100,
        'close': [1.105] * 100,
        'volume': [1000] * 100,
        'atr': [0.002] * 100,
        'rsi': [50] * 100,
        'ema_50': [1.10] * 100
    }, index=dates)
    
    df['regime'] = "RANGING"
    df['atr_ma_20'] = 0.002
    
    m15_dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=100, freq="15min")
    m15_df = df.copy().set_index(m15_dates)
    
    return {'m5': df, 'm15': m15_df, 'h1': df.copy()}

def test_pa_metadata(strategy):
    assert strategy.get_id() == "price_action_specialist"
    assert strategy.get_name() == "Price Action Specialist"

@pytest.mark.asyncio
async def test_pa_regime_filtering(strategy, mock_data):
    # Test regime != RANGING
    mock_data['m5']['regime'] = "TRENDING"
    res = await strategy.analyze("EURUSD=X", mock_data, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_pa_pin_bar_buy(strategy, mock_data):
    # Setup Pin Bar: long lower wick, small body
    latest_idx = mock_data['m5'].index[-1]
    mock_data['m5'].loc[latest_idx, 'open'] = 1.105
    mock_data['m5'].loc[latest_idx, 'close'] = 1.106
    mock_data['m5'].loc[latest_idx, 'low'] = 1.100
    mock_data['m5'].loc[latest_idx, 'high'] = 1.107
    mock_data['m5'].loc[latest_idx, 'ema_50'] = 1.105
    mock_data['m5']['regime'] = "RANGING"
    
    # rsi within range 45-65
    mock_data['m5'].loc[latest_idx, 'rsi'] = 50
    
    with patch("filters.macro_filter.MacroFilter.is_macro_safe", return_value=True):
        with patch("filters.session_filter.SessionFilter.is_valid_session", return_value=True):
            # Mock AI Score - V15.0 Hardened Threshold (8.0)
            strategy.ai_grader.get_score = AsyncMock(return_value=8.5)
            
            res = await strategy.analyze("EURUSD=X", mock_data, [], {})
            
            assert res is not None
            assert res['direction'] == "BUY"
            assert res['setup_quality'] == "PRICE_ACTION"

@pytest.mark.asyncio
async def test_pa_engulfing_sell(strategy, mock_data):
    # Setup Engulfing Sell: latest red engulfs prev green
    latest_idx = mock_data['m5'].index[-1]
    prev_idx = mock_data['m5'].index[-2]
    
    mock_data['m5']['regime'] = "RANGING"
    # Trend bearish (close < ema_50)
    mock_data['m5'].loc[latest_idx, 'ema_50'] = 1.11
    mock_data['m5'].loc[latest_idx, 'close'] = 1.105
    
    mock_data['m5'].loc[prev_idx, 'open'] = 1.106
    mock_data['m5'].loc[prev_idx, 'close'] = 1.107
    mock_data['m5'].loc[prev_idx, 'high'] = 1.108
    mock_data['m5'].loc[prev_idx, 'low'] = 1.105
    
    mock_data['m5'].loc[latest_idx, 'open'] = 1.109
    mock_data['m5'].loc[latest_idx, 'close'] = 1.104
    mock_data['m5'].loc[latest_idx, 'high'] = 1.110
    mock_data['m5'].loc[latest_idx, 'low'] = 1.103
    
    mock_data['m5'].loc[latest_idx, 'rsi'] = 40 # Within 35-55
    
    with patch("filters.macro_filter.MacroFilter.is_macro_safe", return_value=True):
        with patch("filters.session_filter.SessionFilter.is_valid_session", return_value=True):
            # Mock AI Score - V15.0 Hardened Threshold (8.0)
            strategy.ai_grader.get_score = AsyncMock(return_value=9.0)
            
            res = await strategy.analyze("EURUSD=X", mock_data, [], {})
            
            assert res is not None
            assert res['direction'] == "SELL"

@pytest.mark.asyncio
async def test_pa_ai_rejection(strategy, mock_data):
    with patch("indicators.calculations.IndicatorCalculator.get_market_regime", return_value="RANGING"):
        # Setup some valid PA first
        latest_idx = mock_data['m5'].index[-1]
        mock_data['m5'].loc[latest_idx, 'open'] = 1.105
        mock_data['m5'].loc[latest_idx, 'close'] = 1.106
        mock_data['m5'].loc[latest_idx, 'low'] = 1.100
        mock_data['m5'].loc[latest_idx, 'high'] = 1.107
        
        with patch("filters.macro_filter.MacroFilter.is_macro_safe", return_value=True):
            with patch("filters.session_filter.SessionFilter.is_valid_session", return_value=True):
                # Mock Low AI Score
                strategy.ai_grader.get_score = AsyncMock(return_value=5.0)
                
                res = await strategy.analyze("EURUSD=X", mock_data, [], {})
                assert res is None
