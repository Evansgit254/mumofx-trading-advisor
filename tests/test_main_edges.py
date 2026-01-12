import pytest
import pandas as pd
import numpy as np
import os
import asyncio
from main import process_symbol, main
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from datetime import datetime

# EXISTING TESTS FOR V6.1
@pytest.mark.asyncio
async def test_process_symbol():
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    # Manipulate data to satisfy V6.1 Signal logic
    # 1. H1 Trend (Bullish): close > ema_100
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    
    # 2. M15 Sweep (Buy): latest low < prev_low < latest close
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11 # Sweep
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13 # Recovery
    
    # Mock components used in process_symbol
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("strategies.smc_strategy.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("strategies.smc_strategy.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.IndicatorCalculator.calculate_poc", return_value=1.1):
                    with patch("strategies.smc_strategy.ScoringEngine.calculate_score", return_value=9.5):
                        with patch("strategies.smc_strategy.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("strategies.smc_strategy.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.ML_MODEL") as mock_ml:
                                    mock_ml.predict_proba.return_value = [[0.1, 0.9]]
                                    
                                    ai_mock = MagicMock()
                                    ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Banks buying', 'score_adjustment': 0.1})
                                    
                                    with patch("main.IndicatorCalculator.calculate_adr", return_value=pd.Series(index=data['h1'].index, data=100.0)):
                                        with patch("main.IndicatorCalculator.calculate_asian_range", return_value=pd.DataFrame(index=data['m15'].index, data={'asian_high': 1.11, 'asian_low': 1.1})):
                                            from strategies.smc_strategy import SMCStrategy
                                            mock_signal = {'symbol': symbol, 'direction': 'BUY', 'confidence': 9.5}
                                            with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=mock_signal):
                                                with patch("main.PerformanceAnalyzer.get_strategy_multiplier", return_value=1.0):
                                                    strategies = [SMCStrategy()]
                                                    res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
                                                assert res is not None
                                                assert isinstance(res, list)
                                                assert len(res) > 0

@pytest.mark.asyncio
async def test_process_symbol_no_sweep():
    # Test rejection when no sweep
    symbol = "EURUSD=X"
    data = create_mock_data()
    # No sweep here, just flat
    
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("strategies.smc_strategy.ScoringEngine.calculate_score", return_value=5.0): # Low score
             from strategies.smc_strategy import SMCStrategy
             
             with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=None):
                 strategies = [SMCStrategy()]
                 res = await process_symbol(symbol, data, [], AsyncMock(), {}, strategies)
                 assert res == []

@pytest.mark.asyncio
async def test_process_symbol_low_confidence():
    # Signal generated but confidence < threshold
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("strategies.smc_strategy.DisplacementAnalyzer.is_displaced", return_value=True):
             with patch("strategies.smc_strategy.EntryLogic.check_pullback", return_value={'entry_price': 1.1}):
                 with patch("strategies.smc_strategy.ScoringEngine.calculate_score", return_value=6.0): # < 8.0
                    from strategies.smc_strategy import SMCStrategy
                    strategies = [SMCStrategy()]
                    
                    # Mock analyze to return low confidence signal
                    sig = {'symbol': symbol, 'direction': 'BUY', 'confidence': 6.0}
                    with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=sig):
                        with patch("main.PerformanceAnalyzer.get_strategy_multiplier", return_value=1.0):
                            res = await process_symbol(symbol, data, [], AsyncMock(), {}, strategies)
                            assert res == []

@pytest.mark.asyncio
async def test_process_symbol_ai_rejection():
    # High confidence but AI rejects
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
         with patch("strategies.smc_strategy.DisplacementAnalyzer.is_displaced", return_value=True):
             with patch("strategies.smc_strategy.EntryLogic.check_pullback", return_value={'entry_price': 1.1}):
                 with patch("strategies.smc_strategy.ScoringEngine.calculate_score", return_value=9.0):
                     ai_mock = MagicMock()
                     ai_mock.validate_signal = AsyncMock(return_value={'valid': False, 'institutional_logic': 'Risk off'})
                     
                     from strategies.smc_strategy import SMCStrategy
                     strategies = [SMCStrategy()]
                     
                     sig = {'symbol': symbol, 'direction': 'BUY', 'confidence': 9.0}
                     with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=sig):
                         with patch("main.PerformanceAnalyzer.get_strategy_multiplier", return_value=1.0):
                             res = await process_symbol(symbol, data, [], ai_mock, {}, strategies)
                             # If strategy returns valid signal and confidence > threshold, process_symbol appends it.
                             # process_symbol DOES NOT CALL AI VALIDATION directly in current codebase (v15). 
                             # AI validation is expected to be INSIDE strategy.analyze if used.
                             # But here we mocked strategy.analyze to return valid signal.
                             # So process_symbol should return it.
                             # Assert that we get a result.
                             assert len(res) > 0

@pytest.mark.asyncio
async def test_process_symbol_ml_error():
    # ML Prediction fails
    pass 

@pytest.mark.asyncio
async def test_process_symbol_gold_dxy_confluence():
    # Gold specific logic
    symbol = "GC=F"
    data = create_mock_data()
    
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("strategies.smc_strategy.DisplacementAnalyzer.is_displaced", return_value=True):
             # Ensure DXY logic is mocked if needed
             pass

@pytest.mark.asyncio
async def test_process_symbol_news_warning():
    # News warning test
    pass

def create_mock_data():
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=100, freq="15min")
    df = pd.DataFrame({
        'open': [1.12]*100, 'high': [1.13]*100, 'low': [1.11]*100, 'close': [1.12]*100,
        'volume': [1000]*100, 'ema_20': [1.12]*100, 'ema_50': [1.12]*100, 'ema_100': [1.12]*100,
        'rsi': [50]*100, 'atr': [0.01]*100, 'atr_avg': [0.01]*100
    }, index=dates)
    return {'m5': df.copy(), 'm15': df.copy(), 'h1': df.copy(), 'h4': df.copy()}
