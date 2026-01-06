import pytest
import pandas as pd
import numpy as np
from datetime import datetime, time
from indicators.calculations import IndicatorCalculator

@pytest.fixture
def sample_df():
    dates = pd.date_range(start="2024-01-01", periods=300, freq="15min")
    df = pd.DataFrame({
        "open": np.random.uniform(1.0, 1.1, 300),
        "high": np.random.uniform(1.1, 1.2, 300),
        "low": np.random.uniform(0.9, 1.0, 300),
        "close": np.random.uniform(1.0, 1.1, 300),
        "volume": np.random.uniform(100, 1000, 300)
    }, index=dates)
    return df

def test_add_indicators(sample_df):
    result = IndicatorCalculator.add_indicators(sample_df, "15m")
    assert "ema_20" in result.columns
    assert "ema_50" in result.columns
    assert "ema_100" in result.columns
    assert "rsi" in result.columns
    assert "atr" in result.columns
    assert "atr_avg" in result.columns
    assert not result["ema_20"].isna().all()

def test_add_indicators_empty():
    df = pd.DataFrame()
    result = IndicatorCalculator.add_indicators(df, "15m")
    assert result.empty

def test_get_market_structure(sample_df):
    result = IndicatorCalculator.get_market_structure(sample_df)
    assert "hh" in result.columns
    assert "ll" in result.columns

def test_calculate_adr(sample_df):
    # ADR expects H1 data usually, but we can test with our sample
    adr = IndicatorCalculator.calculate_adr(sample_df)
    assert isinstance(adr, float)
    assert adr > 0

def test_calculate_adr_empty():
    assert IndicatorCalculator.calculate_adr(pd.DataFrame()) == 0.0

def test_get_asian_range(sample_df):
    # Ensure some data is in asian session (0-8 UTC)
    result = IndicatorCalculator.get_asian_range(sample_df)
    if result:
        assert "high" in result
        assert "low" in result
        assert result["high"] >= result["low"]

def test_get_asian_range_empty():
    assert IndicatorCalculator.get_asian_range(pd.DataFrame()) is None

def test_calculate_poc(sample_df):
    poc = IndicatorCalculator.calculate_poc(sample_df)
    assert isinstance(poc, float)
    assert poc > 0

def test_calculate_poc_empty():
    assert IndicatorCalculator.calculate_poc(pd.DataFrame()) == 0.0

def test_calculate_poc_single_value():
    df = pd.DataFrame({"high": [1.1], "low": [1.1], "close": [1.1], "volume": [100]})
    assert IndicatorCalculator.calculate_poc(df) == 1.1

def test_calculate_ema_slope(sample_df):
    sample_df["ema_20"] = [i * 0.01 for i in range(len(sample_df))]
    slope = IndicatorCalculator.calculate_ema_slope(sample_df, "ema_20")
    assert slope > 0

def test_calculate_ema_slope_empty():
    assert IndicatorCalculator.calculate_ema_slope(pd.DataFrame(), "ema_20") == 0.0
    df = pd.DataFrame({"ema_20": [1.0]})
    assert IndicatorCalculator.calculate_ema_slope(df, "ema_20") == 0.0
