import pytest
import pandas as pd
import numpy as np
import os
import asyncio
from main import process_symbol, main
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from datetime import datetime

# Existing test_process_symbol remains...
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

# NEW TESTS FOR EDGE CASES

@pytest.mark.asyncio
async def test_process_symbol_neutral_bias():
    """Test when bias is NEUTRAL (line 55)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.BiasAnalyzer.get_bias", return_value="NEUTRAL"):
        ai_mock = MagicMock()
        res = await process_symbol(symbol, data, [], ai_mock, data)
        assert res is None  # Should return None for neutral bias

@pytest.mark.asyncio
async def test_process_symbol_no_sweep():
    """Test when no liquidity sweep detected (lines 61-63)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.LiquidityDetector.detect_sweep", return_value=None):
            ai_mock = MagicMock()
            res = await process_symbol(symbol, data, [], ai_mock, data)
            assert res is None  # Should return None when no sweep

@pytest.mark.asyncio
async def test_process_symbol_low_confidence():
    """Test when confidence < MIN_CONFIDENCE_SCORE (returns None before line 204)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.LiquidityDetector.detect_sweep", return_value={'type': 'M15_SWEEP', 'level': 1.095, 'description': 'Sweep'}):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=3.0):  # Low score
                    ai_mock = Mock()
                    ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Weak', 'score_adjustment': 0})
                    res = await process_symbol(symbol, data, [], ai_mock, data)
                    assert res is None  # Low confidence, no signal

@pytest.mark.asyncio
async def test_process_symbol_ai_rejection():
    """Test when AI rejects signal (lines 164-165)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.LiquidityDetector.detect_sweep", return_value={'type': 'M15_SWEEP', 'level': 1.095, 'description': 'Sweep'}):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    ai_mock = MagicMock()
                    ai_mock.validate_signal = AsyncMock(return_value={'valid': False, 'institutional_logic': 'Retail trap'})
                    res = await process_symbol(symbol, data, [], ai_mock, data)
                    assert res is None  # AI rejected

@pytest.mark.asyncio
async def test_process_symbol_ml_error():
    """Test ML scoring error path (lines 182-183)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.LiquidityDetector.detect_sweep", return_value={'type': 'M15_SWEEP', 'level': 1.095, 'description': 'Sweep'}):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    with patch("main.ML_MODEL") as mock_ml:
                        mock_ml.predict_proba.side_effect = Exception("ML Error")
                        ai_mock = MagicMock()
                        ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Good', 'score_adjustment': 0})
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.IndicatorCalculator.calculate_adr", return_value=100.0):
                                    with patch("main.IndicatorCalculator.get_asian_range", return_value=None):
                                        res = await process_symbol(symbol, data, [], ai_mock, data)
                                        assert res is not None  # Should still work with default win_prob

@pytest.mark.asyncio
async def test_process_symbol_gold_dxy_confluence():
    """Test Gold with DXY confluence (lines 188-198)"""
    symbol = "GC=F"
    data = create_mock_data()
    data_batch = {
        'GC=F': data,
        'DXY': create_mock_data()['h1']  # Add DXY data
    }
    
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.BiasAnalyzer.get_h1_trend", return_value="BEARISH"):  # DXY bearish
            with patch("main.LiquidityDetector.detect_sweep", return_value={'type': 'M15_SWEEP', 'level': 2000, 'description': 'Sweep'}):
                with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 2010, 'ema_zone': 2010, 'rsi_val': 50}):
                    with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.IndicatorCalculator.calculate_adr", return_value=100.0):
                                    with patch("main.IndicatorCalculator.get_asian_range", return_value=None):
                                        ai_mock = MagicMock()
                                        ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Gold buy', 'score_adjustment': 0})
                                        res = await process_symbol(symbol, data, [], ai_mock, data_batch)
                                        assert res is not None
                                        assert "DXY Confluence" in res['confluence']

@pytest.mark.asyncio
async def test_process_symbol_news_warning():
    """Test upcoming news warning (lines 217-220)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    news_events = [
        {'title': 'NFP', 'impact': 'HIGH', 'bias': 'BULLISH', 'minutes_away': 30}
    ]
    
    with patch("main.BiasAnalyzer.get_bias", return_value="BULLISH"):
        with patch("main.LiquidityDetector.detect_sweep", return_value={'type': 'M15_SWEEP', 'level': 1.095, 'description': 'Sweep'}):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    with patch("main.NewsFilter.get_upcoming_events", return_value=news_events):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.IndicatorCalculator.calculate_adr", return_value=100.0):
                                    with patch("main.IndicatorCalculator.get_asian_range", return_value=None):
                                        ai_mock = MagicMock()
                                        ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Good', 'score_adjustment': 0})
                                        res = await process_symbol(symbol, data, news_events, ai_mock, data)
                                        assert res is not None
                                        assert "NEWS WARNING" in res['news_warning']

@pytest.mark.asyncio
async def test_main_error_recovery_local():
    """Test error recovery in local mode (lines 330-334)"""
    with patch.dict(os.environ, {}, clear=True):  # Not GitHub Actions
        with patch("main.NewsFetcher.fetch_news", side_effect=Exception("Network error")):
            with patch("main.TelegramService") as mock_tg_cls:
                mock_tg = MagicMock()
                mock_tg.test_connection = AsyncMock()
                mock_tg_cls.return_value = mock_tg
                with patch("main.AIAnalyst"):
                    with patch("main.TVChartRenderer"):
                        with patch("main.SignalJournal"):
                            # Should sleep and continue, not raise
                            with patch("asyncio.sleep", new_callable=AsyncMock):
                                # Run one iteration then stop
                                task = asyncio.create_task(main())
                                await asyncio.sleep(0.1)
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass

@pytest.mark.asyncio
async def test_main_error_raises_in_actions():
    """Test error raises in GitHub Actions mode (line 331)"""
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
        with patch("main.NewsFetcher.fetch_news", side_effect=ValueError("Test error")):
            with patch("main.TelegramService") as mock_tg_cls:
                mock_tg = MagicMock()
                mock_tg.test_connection = AsyncMock()
                mock_tg_cls.return_value = mock_tg
                with patch("main.AIAnalyst"):
                    with patch("main.TVChartRenderer"):
                        with patch("main.SignalJournal"):
                            with pytest.raises(ValueError):
                                await main()

def create_mock_data():
    """Helper to create mock data quickly"""
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
    
    for df in data.values():
        df['ema_100'] = df['close']
        df['ema_20'] = df['close']
        df['ema_50'] = df['close']
        df['rsi'] = 50
        df['atr'] = 0.01
        df['atr_avg'] = 0.01
    
    return data
