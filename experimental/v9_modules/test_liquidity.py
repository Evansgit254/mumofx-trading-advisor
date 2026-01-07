import pytest
import pandas as pd
import numpy as np
from liquidity.sweep_detector import LiquidityDetector

@pytest.fixture
def sweep_df():
    # 51 candles
    dates = pd.date_range("2024-01-01", periods=60, freq="15min")
    highs = [1.1000] * 59 + [1.1010]
    lows = [1.0900] * 59 + [1.0890]
    closes = [1.0950] * 59 + [1.0970]
    opens = [1.0950] * 59 + [1.0950]
    
    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes
    }, index=dates)
    return df

def test_detect_sweep_bullish(sweep_df):
    # Bullish sweep: latest low < lookback_low and close > lookback_low
    # Lookback low is 1.0900. Latest low is 1.0890. Latest close is 1.0970.
    # wick = min(open, close) - low = 1.0950 - 1.0890 = 0.0060
    # range = 1.1010 - 1.0890 = 0.0120
    # ratio = 0.5 < 0.6. Need a bigger wick.
    
    sweep_df.loc[sweep_df.index[-1], "low"] = 1.0800
    # open 1.0950, close 1.0970, high 1.1010, low 1.0800
    # range = 0.0210. wick = 1.0950 - 1.0800 = 0.0150. ratio = 0.71 > 0.6.
    result = LiquidityDetector.detect_sweep(sweep_df, "BULLISH")
    assert result is not None
    assert "BULLISH_SWEEP" in result["type"]

def test_detect_sweep_bearish(sweep_df):
    sweep_df.loc[sweep_df.index[-1], "high"] = 1.1200
    # open 1.0950, close 1.0970, high 1.1200, low 1.0900
    # range = 0.0300. upper wick = 1.1200 - 1.0970 = 0.0230. ratio = 0.76 > 0.6.
    # Latest close < lookback high (1.1000)
    result = LiquidityDetector.detect_sweep(sweep_df, "BEARISH")
    assert result is not None
    assert "BEARISH_SWEEP" in result["type"]

def test_detect_sweep_none(sweep_df):
    assert LiquidityDetector.detect_sweep(sweep_df, "BULLISH") is None

def test_detect_sweep_empty():
    assert LiquidityDetector.detect_sweep(pd.DataFrame(), "BULLISH") is None
