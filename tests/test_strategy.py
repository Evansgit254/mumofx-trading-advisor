import pytest
import pandas as pd
from strategy.entry import EntryLogic
from strategy.displacement import DisplacementAnalyzer
from datetime import datetime

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

def test_check_pullback_none(entry_df):
    entry_df.loc[1, "rsi"] = 38 # fails crossing 40
    assert EntryLogic.check_pullback(entry_df, "BUY") is None

def test_check_pullback_empty():
    assert EntryLogic.check_pullback(pd.DataFrame(), "BUY") is None

def test_calculate_levels():
    df = pd.DataFrame({"close": [1.1000]})
    # Test NY Session
    t_ny = datetime(2024, 1, 1, 15, 0)
    res = EntryLogic.calculate_levels(df, "BUY", 1.0950, 0.0100, t=t_ny)
    assert res["tp2_mult"] == 2.0
    assert res["tp2"] == 1.1000 + (2.0 * 0.0100)
    
    # Test Asian Session
    t_asian = datetime(2024, 1, 1, 4, 0)
    res = EntryLogic.calculate_levels(df, "SELL", 1.1050, 0.0100, t=t_asian)
    assert res["tp2_mult"] == 1.2

def test_displacement():
    df = pd.DataFrame({
        "open": [1.1000],
        "close": [1.1010],
        "high": [1.1011],
        "low": [1.0999]
    })
    # body = 0.0010, range = 0.0012, ratio = 0.83 > 0.6
    assert bool(DisplacementAnalyzer.is_displaced(df, "BUY")) is True
    assert bool(DisplacementAnalyzer.is_displaced(df, "SELL")) is False

def test_displacement_fail():
    df = pd.DataFrame({
        "open": [1.1000],
        "close": [1.1001],
        "high": [1.1011],
        "low": [1.0999]
    })
    # body = 0.0001, range = 0.0012, ratio = 0.08 < 0.6
    assert bool(DisplacementAnalyzer.is_displaced(df, "BUY")) is False

def test_displacement_empty():
    assert DisplacementAnalyzer.is_displaced(pd.DataFrame(), "BUY") is False
    df = pd.DataFrame({"open": [1.0], "close": [1.0], "high": [1.0], "low": [1.0]})
    assert DisplacementAnalyzer.is_displaced(df, "BUY") is False

from strategy.scoring import ScoringEngine

def test_scoring_engine():
    details = {
        'h1_aligned': True,
        'sweep_type': 'M15',
        'displaced': True,
        'pullback': True,
        'volatile': True,
        'symbol': 'EURUSD'
    }
    # 3.0 + 3.0 + 2.0 + 1.5 + 0.5 = 10.0
    assert ScoringEngine.calculate_score(details) == 10.0

def test_scoring_engine_gold():
    details = {
        'h1_aligned': False,
        'symbol': 'GC=F'
    }
    # 1.5 - 5.0 = -3.5
    assert ScoringEngine.calculate_score(details) == -3.5
    
    details['h1_aligned'] = True
    details['asian_sweep'] = True
    details['asian_quality'] = False
    # 3.0 - 3.0 - 1.5 = -1.5
    assert ScoringEngine.calculate_score(details) == -1.5

def test_scoring_engine_jpy_index():
    details = {'symbol': 'USDJPY', 'h1_aligned': True}
    # 3.0 + 1.0 = 4.0
    assert ScoringEngine.calculate_score(details) == 4.0
    
    details = {'symbol': '^IXIC', 'h1_aligned': True}
    # 3.0 + 1.0 = 4.0
    assert ScoringEngine.calculate_score(details) == 4.0

def test_scoring_engine_slope_filters():
    # BUY and steep down slope
    details = {'direction': 'BUY', 'ema_slope': -0.1, 'h1_aligned': True}
    # 3.0 - 2.0 = 1.0
    assert ScoringEngine.calculate_score(details) == 1.0
    
    # SELL and steep up slope
    details = {'direction': 'SELL', 'ema_slope': 0.1, 'h1_aligned': True}
    # 3.0 - 2.0 = 1.0
    assert ScoringEngine.calculate_score(details) == 1.0

def test_scoring_engine_overextended():
    details = {'h1_dist': 0.01, 'h1_aligned': True}
    # 3.0 - 2.0 = 1.0
    assert ScoringEngine.calculate_score(details) == 1.0
