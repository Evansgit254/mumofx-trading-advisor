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
        'm5': mock_df.copy().set_index(m5_dates)
    }
    
    # Add dummy indicators that process_symbol might expect before calculation
    for df in data.values():
        df['ema_100'] = df['close']
        df['ema_20'] = df['close']
        df['ema_50'] = df['close']
        df['rsi'] = 50
        df['atr'] = 0.01
        df['atr_avg'] = 0.01
    
    # Mock components used in process_symbol
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.LiquidityDetector.detect_sweep", return_value={'type': 'M15_SWEEP', 'level': 1.095, 'description': 'Sweep'}):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.IndicatorCalculator.calculate_poc", return_value=1.1):
                    with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.ML_MODEL") as mock_ml:
                                    mock_ml.predict_proba.return_value = [[0.1, 0.9]]
                                    
                                    ai_mock = MagicMock()
                                    ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Banks buying', 'score_adjustment': 0.1})
                                    
                                    # We also need to mock some globals if they aren't available or if logic expects them
                                    with patch("main.IndicatorCalculator.calculate_adr", return_value=100.0):
                                        with patch("main.IndicatorCalculator.get_asian_range", return_value={'high': 1.11, 'low': 1.1}):
                                            res = await process_symbol(symbol, data, [], ai_mock, data)
                                            assert res is not None
                                            assert res['symbol'] == symbol
                                            assert res['confidence'] >= 9.0  # ScoringEngine returns 9.5
