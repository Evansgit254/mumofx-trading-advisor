import pytest
import pandas as pd
import numpy as np
from indicators.calculations import IndicatorCalculator
from strategy.crt import CRTAnalyzer

def test_detect_crt_phases_accumulation():
    # Setup data with consolidation
    dates = pd.date_range(start="2024-01-01", periods=100, freq="15min")
    df = pd.DataFrame({
        'open': [1.1000] * 100,
        'high': [1.1010] * 100,
        'low': [1.0990] * 100,
        'close': [1.1000] * 100,
        'volume': [1000] * 100
    }, index=dates)
    
    # CRT lookback is 24.
    # Current bar is at index 99.
    # Subset is df.iloc[-29:-5] -> bars 71 to 94. 
    # Manipulation check on last 5 bars: 95 to 99.
    
    result = IndicatorCalculator.detect_crt_phases(df)
    assert result is not None
    assert result['phase'] == "ACCUMULATION"

def test_detect_crt_phases_distribution_long():
    dates = pd.date_range(start="2024-01-01", periods=100, freq="15min")
    data = []
    for i in range(100):
        if i < 90:
            # Accumulation Range: 1.0990 - 1.1010
            data.append([1.1000, 1.1010, 1.0990, 1.1000])
        elif i == 95:
            # Manipulation: Sweep low
            data.append([1.1000, 1.1010, 1.0980, 1.1000])
        elif i >= 96:
            # Distribution: Expansion up
            data.append([1.1000, 1.1050, 1.1000, 1.1040])
        else:
            data.append([1.1000, 1.1010, 1.0990, 1.1000])
            
    df = pd.DataFrame(data, columns=['open', 'high', 'low', 'close'], index=dates)
    df['volume'] = 1000
    
    result = IndicatorCalculator.detect_crt_phases(df)
    assert result['phase'] == "DISTRIBUTION_LONG"
    
    # Validate with CRTAnalyzer
    validation = CRTAnalyzer.validate_setup(df, "BUY")
    assert validation['valid'] is True
    assert validation['score_bonus'] == 1.0

def test_calculate_h4_levels():
    dates = pd.date_range(start="2024-01-01", periods=20, freq="4h")
    df = pd.DataFrame({
        'high': [1.1050] * 20,
        'low': [1.0950] * 20,
        'close': [1.1000] * 20
    }, index=dates)
    
    levels = IndicatorCalculator.calculate_h4_levels(df)
    assert 'h4_high' in levels.columns
    assert 'h4_low' in levels.columns
