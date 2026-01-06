import pytest
import pandas as pd
from filters.risk_manager import RiskManager
from filters.correlation import CorrelationAnalyzer
from filters.session_filter import SessionFilter
from filters.volatility_filter import VolatilityFilter
from config.config import ACCOUNT_BALANCE, MIN_LOT_SIZE

def test_risk_manager_lots():
    # Test EURUSD (pip_val=0.10)
    # Entry 1.1000, SL 1.0900 -> 100 pips
    # Risk 2% of $50 = $1.00
    # Expected lots = (1.0 / (0.10 * 100)) * 0.01 = 0.01
    res = RiskManager.calculate_lot_size("EURUSD=X", 1.1000, 1.0900)
    assert res["lots"] == 0.01
    assert res["pips"] == 100.0

def test_risk_manager_gold():
    # Gold (GC) uses points
    res = RiskManager.calculate_lot_size("GC=F", 2000.0, 1990.0)
    assert res["pips"] == 10.0
    assert res["lots"] >= 0.01

def test_risk_manager_layers():
    layers = RiskManager.calculate_layers(0.03, 1.1000, 1.0900, "BUY")
    assert len(layers) == 3
    assert layers[0]["lots"] == 0.01 # 40% of 0.03 = 0.012 -> 0.01
    assert layers[2]["lots"] == 0.01 # 20% of 0.03 = 0.006 -> 0.01
    assert layers[1]["price"] < 1.1000

def test_correlation_analyzer():
    signals = [
        {'pair': 'EURUSD', 'direction': 'BUY', 'win_prob': 0.8},
        {'pair': 'GBPUSD', 'direction': 'SELL', 'win_prob': 0.6}
    ]
    # BUY EURUSD -> Short USD
    # SELL GBPUSD -> Long USD
    # Conflict!
    filtered = CorrelationAnalyzer.filter_signals(signals)
    assert len(filtered) == 1
    assert filtered[0]['pair'] == 'EURUSD'

def test_correlation_analyzer_no_conflict():
    signals = [
        {'pair': 'EURUSD', 'direction': 'BUY', 'win_prob': 0.8},
        {'pair': 'USDJPY', 'direction': 'BUY', 'win_prob': 0.7}
    ]
    # BUY EURUSD -> Short USD
    # BUY USDJPY -> Long USD
    # Conflict!
    filtered = CorrelationAnalyzer.filter_signals(signals)
    assert len(filtered) == 1

from unittest.mock import patch
from datetime import datetime
import pytz

def test_session_filter():
    assert isinstance(SessionFilter.is_valid_session(), bool)

def test_session_extended_logic():
    # Test 17:00 UTC (Inside Extended Window: 13:00 - 18:00)
    with patch('filters.session_filter.datetime') as mock_dt:
        mock_now = datetime(2026, 1, 1, 17, 0, 0, tzinfo=pytz.UTC)
        mock_dt.now.return_value = mock_now
        
        assert SessionFilter.is_valid_session() is True
        assert SessionFilter.get_session_name() == "London-NY Overlap (Extended)"

    # Test 19:00 UTC (Outside Extended Window)
    with patch('filters.session_filter.datetime') as mock_dt:
        mock_now = datetime(2026, 1, 1, 19, 0, 0, tzinfo=pytz.UTC)
        mock_dt.now.return_value = mock_now
        
        assert SessionFilter.is_valid_session() is False
        assert SessionFilter.get_session_name() == "Outside Session"

def test_volatility_filter():
    df = pd.DataFrame({
        'atr': [0.0001, 0.0001], 
        'atr_avg': [0.0001, 0.0001]
    })
    # Volatility filter returns atr > atr_avg and atr >= prev_atr
    assert bool(VolatilityFilter.is_volatile(df)) is False
    
    df = pd.DataFrame({
        'atr': [0.0002, 0.0003], 
        'atr_avg': [0.0001, 0.0002]
    })
    assert bool(VolatilityFilter.is_volatile(df)) is True
