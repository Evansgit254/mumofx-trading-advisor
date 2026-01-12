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
    # V12.0: 1.5 (base) - 2.5 (H1) - 1.0 (No displacement) - 3.0 (Trap: no displaced/fvg) = -5.0
    assert ScoringEngine.calculate_score(details) == -5.0
    
    details['h1_aligned'] = True
    details['asian_sweep'] = True
    details['asian_quality'] = False
    # V12.0: 3.0 (base) - 1.5 (asian sweep) - 3.0 (gold asian) - 1.0 (no displacement) - 3.0 (trap: both missing) = -5.5
    assert ScoringEngine.calculate_score(details) == -5.5

def test_scoring_engine_jpy_index():
    details = {'symbol': 'USDJPY', 'h1_aligned': True}
    # 3.0 (base) + 1.0 (Alpha) - 1.0 (No displacement) = 3.0
    assert ScoringEngine.calculate_score(details) == 3.0
    
    details = {'symbol': '^IXIC', 'h1_aligned': True}
    assert ScoringEngine.calculate_score(details) == 3.0

def test_scoring_engine_slope_filters():
    details = {'direction': 'BUY', 'ema_slope': -0.1, 'h1_aligned': True}
    # 3.0 (base) - 1.0 (No displacement) = 2.0 (No slope penalty in V12.0)
    assert ScoringEngine.calculate_score(details) == 2.0
    
    details = {'direction': 'SELL', 'ema_slope': 0.1, 'h1_aligned': True}
    assert ScoringEngine.calculate_score(details) == 2.0

def test_scoring_engine_overextended():
    details = {'h1_dist': 0.01, 'h1_aligned': True}
    # 3.0 (base) - 2.0 (Extension) - 1.0 (No displacement) = 0.0
    assert ScoringEngine.calculate_score(details) == 0.0
