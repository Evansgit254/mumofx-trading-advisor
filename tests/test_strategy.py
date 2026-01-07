import pytest
import pandas as pd
from strategy.entry import EntryLogic
from strategy.displacement import DisplacementAnalyzer
from datetime import datetime
from strategy.scoring import ScoringEngine

@pytest.fixture
def entry_df():
    return pd.DataFrame({
        "close": [1.1000, 1.1010],
        "low": [1.0990, 1.0995],
        "high": [1.1010, 1.1020],
        "ema_20": [1.0998, 1.1002],
        "rsi": [35, 45]
    })

def test_check_pullback_buy(entry_df):
    # Buy condition: prev rsi <= 40, latest > 40, low <= ema20 * 1.001
    result = EntryLogic.check_pullback(entry_df, "BUY")
    assert result is not None
    assert result["entry_price"] == 1.1010

def test_check_pullback_sell():
    df = pd.DataFrame({
        "close": [1.1020, 1.1010],
        "high": [1.1030, 1.1025],
        "low": [1.1010, 1.1005],
        "ema_20": [1.1022, 1.1018],
        "rsi": [65, 55]
    })
    result = EntryLogic.check_pullback(df, "SELL")
    assert result is not None
    assert result["entry_price"] == 1.1010

def test_calculate_levels():
    df = pd.DataFrame({"close": [1.1000]})
    # Test NY Session
    t_ny = datetime(2024, 1, 1, 15, 0)
    res = EntryLogic.calculate_levels(df, "BUY", 1.0950, 0.0100, t=t_ny)
    assert res["tp2_mult"] == 2.0
    assert res["tp2"] == 1.1000 + (2.0 * 0.0100)

def test_displacement():
    df = pd.DataFrame({
        "open": [1.1000],
        "close": [1.1010],
        "high": [1.1011],
        "low": [1.0999]
    })
    assert bool(DisplacementAnalyzer.is_displaced(df, "BUY")) is True

def test_scoring_engine():
    details = {
        'h1_aligned': True,
        'sweep_type': 'M15',
        'displaced': True,
        'pullback': True,
        'volatile': True,
        'symbol': 'EURUSD'
    }
    # 3.0 (H1) + 3.0 (M15) + 2.0 (Displaced) + 1.5 (Pullback) + 0.5 (Volatile) = 10.0
    assert ScoringEngine.calculate_score(details) == 10.0

def test_scoring_engine_gold():
    details = {
        'h1_aligned': False,
        'symbol': 'GC=F'
    }
    # V8.1: 1.5 (base) - 5.0 (H1) - 2.0 (No displacement) - 4.0 (Trap: no displaced/fvg) = -9.5
    assert ScoringEngine.calculate_score(details) == -9.5
    
    details['h1_aligned'] = True
    details['asian_sweep'] = True
    details['asian_quality'] = False
    # V8.1: 3.0 (base) - 1.5 (asian sweep) - 3.0 (gold asian) - 2.0 (no displacement) - 4.0 (trap) = -7.5
    assert ScoringEngine.calculate_score(details) == -7.5

def test_scoring_engine_jpy_index():
    details = {'symbol': 'USDJPY', 'h1_aligned': True}
    # 3.0 (base) + 1.0 (Alpha) - 2.0 (No displacement) = 2.0
    assert ScoringEngine.calculate_score(details) == 2.0
    
    details = {'symbol': '^IXIC', 'h1_aligned': True}
    assert ScoringEngine.calculate_score(details) == 2.0

def test_scoring_engine_slope_filters():
    details = {'direction': 'BUY', 'ema_slope': -0.1, 'h1_aligned': True}
    # 3.0 (base) - 2.0 (Slope) - 2.0 (No displacement) = -1.0
    assert ScoringEngine.calculate_score(details) == -1.0
    
    details = {'direction': 'SELL', 'ema_slope': 0.1, 'h1_aligned': True}
    assert ScoringEngine.calculate_score(details) == -1.0

def test_scoring_engine_overextended():
    details = {'h1_dist': 0.01, 'h1_aligned': True}
    # 3.0 (base) - 2.0 (Extension) - 2.0 (No displacement) = -1.0
    assert ScoringEngine.calculate_score(details) == -1.0
