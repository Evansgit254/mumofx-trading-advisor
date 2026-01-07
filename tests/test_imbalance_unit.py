import pytest
import pandas as pd
from strategy.imbalance import ImbalanceDetector

def test_detect_fvg_short_df():
    df = pd.DataFrame({'low': [1, 2], 'high': [3, 4]})
    assert ImbalanceDetector.detect_fvg(df) == []

def test_detect_fvg_bullish():
    # Bullish FVG: Low of candle 3 > High of candle 1
    data = {
        'low':  [1.0, 1.2, 1.5],
        'high': [1.1, 1.8, 2.0]
    }
    df = pd.DataFrame(data)
    fvgs = ImbalanceDetector.detect_fvg(df)
    assert len(fvgs) == 1
    assert fvgs[0]['type'] == 'BULLISH'
    assert fvgs[0]['top'] == 1.5  # c3 low
    assert fvgs[0]['bottom'] == 1.1 # c1 high

def test_detect_fvg_bearish():
    # Bearish FVG: High of candle 3 < Low of candle 1
    data = {
        'low':  [1.9, 1.2, 1.0],
        'high': [2.0, 1.8, 1.1]
    }
    df = pd.DataFrame(data)
    fvgs = ImbalanceDetector.detect_fvg(df)
    assert len(fvgs) == 1
    assert fvgs[0]['type'] == 'BEARISH'
    assert fvgs[0]['top'] == 1.9    # c1 low
    assert fvgs[0]['bottom'] == 1.1 # c3 high

def test_detect_fvg_none():
    data = {
        'low':  [1.0, 1.1, 1.2],
        'high': [1.5, 1.6, 1.7]
    }
    df = pd.DataFrame(data)
    assert ImbalanceDetector.detect_fvg(df) == []

def test_is_price_in_fvg():
    fvgs = [
        {'type': 'BULLISH', 'top': 1.5, 'bottom': 1.1},
        {'type': 'BEARISH', 'top': 2.0, 'bottom': 1.8}
    ]
    # BUY + Bullish FVG
    assert ImbalanceDetector.is_price_in_fvg(1.3, fvgs, "BUY") is True
    assert ImbalanceDetector.is_price_in_fvg(1.6, fvgs, "BUY") is False # Too high
    
    # SELL + Bearish FVG
    assert ImbalanceDetector.is_price_in_fvg(1.9, fvgs, "SELL") is True
    assert ImbalanceDetector.is_price_in_fvg(1.7, fvgs, "SELL") is False # Too low
    
    # Empty fvgs
    assert ImbalanceDetector.is_price_in_fvg(1.3, [], "BUY") is False

def test_detect_fvg_limit():
    # Test the loop limit (last 10 bars)
    data = {
        'low':  [1.0]*20,
        'high': [1.1]*20
    }
    df = pd.DataFrame(data)
    # Create an FVG way back (index 5)
    df.loc[5, 'high'] = 1.05
    df.loc[6, 'low'] = 1.2
    df.loc[6, 'high'] = 1.3
    df.loc[7, 'low'] = 1.25
    
    # This FVG is at index 6 (7-5 is the 3-candle sequence)
    # The loop goes from range(len-3, len-13, -1)
    # If len=20, range(17, 7, -1). So index 6 is NOT should not be reached.
    assert ImbalanceDetector.detect_fvg(df) == []
    
    # Now create one at index 15
    df.loc[14, 'high'] = 1.05
    df.loc[15, 'low'] = 1.2
    df.loc[16, 'low'] = 1.25
    # FVG sequence: 14, 15, 16. i = 14. 
    # Loop i=17, 16, 15, 14... 14 should be hit.
    assert len(ImbalanceDetector.detect_fvg(df)) >= 1
