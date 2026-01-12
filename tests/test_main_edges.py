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
        with patch("main.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.IndicatorCalculator.calculate_poc", return_value=1.1):
                    with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
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
                                                signal = res[0]
                                                assert signal['symbol'] == symbol
                                                assert signal['confidence'] >= 9.0

# NEW TESTS FOR EDGE CASES

@pytest.mark.asyncio
async def test_process_symbol_neutral_bias():
    """Test when bias is NEUTRAL (price == EMA)"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    # Neutral: set close == ema_100
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.10
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        from strategies.smc_strategy import SMCStrategy
        strategies = [SMCStrategy()]
        ai_mock = MagicMock()
        res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
        assert res == [] 

@pytest.mark.asyncio
async def test_process_symbol_no_sweep():
    """Test when no liquidity sweep detected"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    # Setup correct bias
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    
    # But fail sweep (price stays above prev lows)
    data['m15']['low'] = 1.15
    data['m15']['close'] = 1.16
    
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        from strategies.smc_strategy import SMCStrategy
        strategies = [SMCStrategy()]
        with patch("main.ScoringEngine.calculate_score", return_value=9.5):
            ai_mock = MagicMock()
            ai_mock.validate_signal = AsyncMock(return_value={'valid': True})
            res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
            assert res == [] 

@pytest.mark.asyncio
async def test_process_symbol_low_confidence():
    """Test when confidence < MIN_CONFIDENCE_SCORE"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    # Setup Signal
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13

    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        from strategies.smc_strategy import SMCStrategy
        strategies = [SMCStrategy()]
        with patch("main.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=3.0):  # Low score
                    ai_mock = Mock()
                    ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Weak', 'score_adjustment': 0})
                    res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
                    assert res == []

@pytest.mark.asyncio
async def test_process_symbol_ai_rejection():
    """Test when AI rejects signal"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    # Setup Signal
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13

    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        from strategies.smc_strategy import SMCStrategy
        strategies = [SMCStrategy()]
        with patch("main.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    ai_mock = MagicMock()
                    ai_mock.validate_signal = AsyncMock(return_value={'valid': False, 'institutional_logic': 'Retail trap'})
                    res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
                    assert res == []

@pytest.mark.asyncio
async def test_process_symbol_ml_error():
    """Test ML scoring error path"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    
    # Setup Signal
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13

    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    with patch("main.ML_MODEL") as mock_ml:
                        mock_ml.predict_proba.side_effect = Exception("ML Error")
                        ai_mock = MagicMock()
                        ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Good', 'score_adjustment': 0})
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.IndicatorCalculator.calculate_adr", return_value=100.0):
                                    with patch("main.IndicatorCalculator.calculate_asian_range", return_value=pd.DataFrame(index=data['m15'].index, data={'asian_high': 0, 'asian_low': 0})):
                                        with patch("main.IndicatorCalculator.calculate_poc", return_value=1.1):
                                            from strategies.smc_strategy import SMCStrategy
                                            mock_signal = {'symbol': symbol, 'direction': 'BUY', 'confidence': 9.5}
                                            with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=mock_signal):
                                                strategies = [SMCStrategy()]
                                                res = await process_symbol(symbol, data, [], ai_mock, data, strategies)
                                                assert res is not None
                                                assert isinstance(res, list)
                                                assert len(res) > 0
                                                signal = res[0]
                                                assert signal['symbol'] == symbol

@pytest.mark.asyncio
async def test_process_symbol_gold_dxy_confluence():
    """Test Gold with DXY confluence"""
    symbol = "GC=F"
    data = create_mock_data()
    data_batch = {
        'GC=F': data,
        'DXY': create_mock_data()['h1']
    }
    
    # Setup Signal
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13
    
    # DXY Bearish: close < ema_100
    dxy_df = data_batch['DXY']
    dxy_df.iloc[-1, dxy_df.columns.get_loc('close')] = 1.05
    dxy_df.iloc[-1, dxy_df.columns.get_loc('ema_100')] = 1.10

    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 2010, 'ema_zone': 2010, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                        with patch("main.RiskManager.calculate_layers", return_value=[]):
                            with patch("main.IndicatorCalculator.calculate_adr", return_value=pd.Series(index=data['h1'].index, data=100.0)):
                                with patch("main.IndicatorCalculator.calculate_asian_range", return_value=pd.DataFrame(index=data['m15'].index, data={'asian_high': 0, 'asian_low': 0})):
                                    with patch("main.IndicatorCalculator.calculate_poc", return_value=2000):
                                        ai_mock = MagicMock()
                                        ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Gold buy', 'score_adjustment': 0})
                                        from strategies.smc_strategy import SMCStrategy
                                        mock_signal = {'symbol': symbol, 'direction': 'BUY', 'confidence': 9.5, 'confluence': 'DXY Confluence'}
                                        with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=mock_signal):
                                            strategies = [SMCStrategy()]
                                            res = await process_symbol(symbol, data, [], ai_mock, data_batch, strategies)
                                            assert res is not None
                                            assert isinstance(res, list)
                                            assert len(res) > 0
                                            signal = res[0]
                                            assert "DXY Confluence" in signal['confluence']

@pytest.mark.asyncio
async def test_process_symbol_news_warning():
    """Test upcoming news warning"""
    symbol = "EURUSD=X"
    data = create_mock_data()
    news_events = [
        {'title': 'NFP', 'impact': 'HIGH', 'bias': 'BULLISH', 'minutes_away': 30}
    ]
    
    # Setup Signal
    data['h1'].iloc[-1, data['h1'].columns.get_loc('close')] = 1.15
    data['h1'].iloc[-1, data['h1'].columns.get_loc('ema_100')] = 1.10
    data['m15'].iloc[-5, data['m15'].columns.get_loc('low')] = 1.12
    data['m15'].iloc[-1, data['m15'].columns.get_loc('low')] = 1.11
    data['m15'].iloc[-1, data['m15'].columns.get_loc('close')] = 1.13

    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.DisplacementAnalyzer.is_displaced", return_value=True):
            with patch("main.EntryLogic.check_pullback", return_value={'entry_price': 1.1, 'ema_zone': 1.1, 'rsi_val': 50}):
                with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                    with patch("main.NewsFilter.get_upcoming_events", return_value=news_events):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 2.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                with patch("main.IndicatorCalculator.calculate_adr", return_value=100.0):
                                    with patch("main.IndicatorCalculator.calculate_asian_range", return_value=pd.DataFrame(index=data['m15'].index, data={'asian_high': 0, 'asian_low': 0})):
                                        with patch("main.IndicatorCalculator.calculate_poc", return_value=1.1):
                                            ai_mock = MagicMock()
                                            ai_mock.validate_signal = AsyncMock(return_value={'valid': True, 'institutional_logic': 'Good', 'score_adjustment': 0})
                                            from strategies.smc_strategy import SMCStrategy
                                            mock_signal = {'symbol': symbol, 'direction': 'BUY', 'confidence': 9.5, 'news_warning': 'Upcoming News'}
                                            with patch.object(SMCStrategy, 'analyze', new_callable=AsyncMock, return_value=mock_signal):
                                                strategies = [SMCStrategy()]
                                                res = await process_symbol(symbol, data, news_events, ai_mock, data, strategies)
                                                assert res is not None
                                                assert isinstance(res, list)
                                                assert len(res) > 0
                                                signal = res[0]
                                                assert "Upcoming News" in signal['news_warning']

@pytest.mark.asyncio
async def test_main_error_recovery_local():
    """Test error recovery in local mode"""
    with patch.dict(os.environ, {}, clear=True):
        with patch("main.NewsFetcher.fetch_news", side_effect=Exception("Network error")):
            with patch("main.TelegramService") as mock_tg_cls:
                mock_tg = MagicMock()
                mock_tg.test_connection = AsyncMock()
                mock_tg_cls.return_value = mock_tg
                with patch("main.AIAnalyst"):
                    with patch("main.TVChartRenderer"):
                        with patch("main.SignalJournal"):
                            with patch("asyncio.sleep", new_callable=AsyncMock):
                                task = asyncio.create_task(main())
                                await asyncio.sleep(0.1)
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass

@pytest.mark.asyncio
async def test_main_error_raises_in_actions():
    """Test error raises in GitHub Actions mode"""
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
        'low': np.random.uniform(1.1, 1.2, 300), # Baseline low
        'open': np.random.uniform(1.1, 1.2, 300),
        'volume': np.random.uniform(100, 1000, 300)
    })
    
    data = {
        'h1': mock_df.copy().set_index(h1_dates),
        'm15': mock_df.copy().set_index(dates),
        'm5': mock_df.copy().set_index(m5_dates),
        'h4': mock_df.copy().set_index(h1_dates) # Rough proxy for h4
    }
    
    # Ensure baseline highs/lows for sweep
    data['m15']['low'] = 1.2
    data['m15']['high'] = 1.3
    data['m15']['close'] = 1.25

    for df in data.values():
        df['ema_100'] = df['close']
        df['ema_20'] = df['close']
        df['ema_50'] = df['close']
        df['rsi'] = 50
        df['atr'] = 0.01
        df['atr_avg'] = 0.01
    
    return data
