import pytest
import pandas as pd
import numpy as np
from main import process_symbol
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
async def test_process_symbol():
    symbol = "EURUSD=X"
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=300, freq="15min")
    h1_dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=300, freq="1h")
    m5_dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=300, freq="5min")
    
    mock_df = pd.DataFrame({
        'close': np.random.uniform(1.1, 1.2, 300),
        'high': np.random.uniform(1.2, 1.3, 300),
        'low': np.random.uniform(1.0, 1.1, 300),
        'open': np.random.uniform(1.1, 1.2, 300),
        'volume': np.random.uniform(100, 1000, 300)
    })
    
    data = {
        'h1': mock_df.copy().set_index(h1_dates),
        'm15': mock_df.copy().set_index(dates),
        'm5': mock_df.copy().set_index(m5_dates),
        'h4': mock_df.copy().set_index(h1_dates) # Rough proxy for h4
    }
    
    # Ensure all lows are high enough so a 1.10 sweep works
    data['m15']['low'] = 1.2
    data['m15']['high'] = 1.3
    data['m15']['close'] = 1.25
    
    # Add dummy indicators that process_symbol might expect before calculation
    for df in data.values():
        df['ema_100'] = df['close']
        df['ema_20'] = df['close']
        df['ema_50'] = df['close']
        df['rsi'] = 50
        df['atr'] = 0.01
        df['atr_avg'] = 0.01
    
    # Manipulate data to satisfy V6.1 Signal logic
    # 1. H1 Trend (Bullish): close > ema_100
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    
    # 2. M15 Sweep (Buy): latest low < prev_low < latest close
    # prev_low is min of previous 21 bars
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11 # Sweep
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13 # Recovery
    
    # Mock components used in process_symbol
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("strategy.displacement.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("strategy.entry.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.IndicatorCalculator.calculate_poc", return_value=1.1):
                    with patch("strategy.scoring.ScoringEngine.calculate_score", return_value=9.5):
                        with patch("filters.risk_manager.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("filters.risk_manager.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.ML_MODEL") as mock_ml:
                                    mock_ml.predict_proba.return_value = [[0.1, 0.9]]
                                    
                                    ai_mock = MagicMock()
                                    ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Banks buying', 'score_adjustment': 0.1})
                                    
                                    with patch("main.IndicatorCalculator.calculate_adr", return_value=pd.Series(index=data['h1'].index, data=100.0)):
                                        with patch("main.IndicatorCalculator.calculate_asian_range", return_value=pd.DataFrame(index=data['m15'].index, data={'asian_high': 1.11, 'asian_low': 1.1})):
                                            from strategies.smc_strategy import SMCStrategy
                                            mock_signal = {
                                                'symbol': symbol,
                                                'direction': 'BUY',
                                                'confidence': 9.5,
                                                'entry_price': 1.1,
                                                'sl': 1.0,
                                                'tp0': 1.2,
                                                'tp1': 1.3,
                                                'tp2': 1.4
                                            }
                                            with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=mock_signal):
                                                with patch("main.PerformanceAnalyzer.get_strategy_multiplier", return_value=1.0):
                                                    strategies = [SMCStrategy()]
                                                    res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
                                                assert res is not None
                                                assert isinstance(res, list)
                                                assert len(res) > 0
                                                signal = res[0]
                                                assert signal['symbol'] == symbol
                                                assert signal['confidence'] >= 9.0  # ScoringEngine returns 9.5
