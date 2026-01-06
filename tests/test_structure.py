import pytest
import pandas as pd
from structure.bias import BiasAnalyzer

@pytest.fixture
def bias_dfs():
    h1_df = pd.DataFrame({
        "close": [1.1000],
        "ema_100": [1.0900]
    })
    m15_df = pd.DataFrame({
        "close": [1.1000],
        "ema_20": [1.1010],
        "ema_50": [1.1005]
    })
    return h1_df, m15_df

def test_bias_bullish(bias_dfs):
    h1_df, m15_df = bias_dfs
    m15_df.loc[0, "ema_20"] = 1.1050
    m15_df.loc[0, "ema_50"] = 1.1020
    m15_df.loc[0, "close"] = 1.1060
    # H1: 1.1000 > 1.0900 -> BULLISH
    # M15: 1.1060 > 1.1050 > 1.1020 -> BULLISH
    assert BiasAnalyzer.get_bias(h1_df, m15_df) == "BULLISH"

def test_bias_bearish(bias_dfs):
    h1_df, m15_df = bias_dfs
    h1_df.loc[0, "close"] = 1.0800
    m15_df.loc[0, "ema_20"] = 1.1000
    m15_df.loc[0, "ema_50"] = 1.1020
    m15_df.loc[0, "close"] = 1.0990
    # H1: 1.0800 < 1.0900 -> BEARISH
    # M15: 1.0990 < 1.1000 < 1.1020 -> BEARISH
    assert BiasAnalyzer.get_bias(h1_df, m15_df) == "BEARISH"

def test_bias_neutral(bias_dfs):
    h1_df, m15_df = bias_dfs
    # H1: BULLISH, M15: NEUTRAL/BEARISH
    assert BiasAnalyzer.get_bias(h1_df, m15_df) == "NEUTRAL"

def test_bias_empty():
    assert BiasAnalyzer.get_bias(pd.DataFrame(), pd.DataFrame()) == "NEUTRAL"

def test_get_h1_trend(bias_dfs):
    h1_df, _ = bias_dfs
    assert BiasAnalyzer.get_h1_trend(h1_df) == "BULLISH"
    h1_df.loc[0, "close"] = 1.0800
    assert BiasAnalyzer.get_h1_trend(h1_df) == "BEARISH"
