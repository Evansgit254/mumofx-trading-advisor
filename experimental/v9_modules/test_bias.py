import pandas as pd
import pytest
from structure.bias import BiasAnalyzer
from config.config import EMA_TREND

def test_get_h1_trend_bullish():
    # Mock H1 data
    df = pd.DataFrame({
        'close': [1.1000, 1.1050],
        f'ema_{EMA_TREND}': [1.1010, 1.1020]
    })
    trend = BiasAnalyzer.get_h1_trend(df)
    assert trend == "BULLISH"

def test_get_h1_trend_bearish():
    df = pd.DataFrame({
        'close': [1.1000, 1.0990],
        f'ema_{EMA_TREND}': [1.1010, 1.1020]
    })
    trend = BiasAnalyzer.get_h1_trend(df)
    assert trend == "BEARISH"

def test_get_bias_neutral_on_empty():
    assert BiasAnalyzer.get_bias(pd.DataFrame(), pd.DataFrame()) == "NEUTRAL"
