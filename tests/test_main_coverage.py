import pytest
import pandas as pd
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock
from main import process_symbol, main

class BreakLoop(BaseException): 
    """Custom exception to break out of main loop in tests"""
    pass

@pytest.fixture
def mock_data():
    """Standard mock data with all required columns"""
    timestamp = pd.Timestamp.now(tz="UTC")
    df = pd.DataFrame({
        'open': [1.05] * 100,
        'high': [1.1] * 100,
        'low': [1.0] * 100,
        'close': [1.05] * 100,
        'volume': [1000] * 100,
        'ema_20': [1.05] * 100,
        'ema_50': [1.05] * 100,
        'ema_100': [1.05] * 100,
        'rsi': [50] * 100,
        'atr': [0.01] * 100,
        'atr_avg': [0.01] * 100,
    }, index=[timestamp - pd.Timedelta(minutes=5*i) for i in range(100)][::-1])
    return {'m5': df.copy(), 'm15': df.copy(), 'h1': df.copy()}

# ========== process_symbol Tests ==========

@pytest.mark.asyncio
async def test_news_rejection(mock_data):
    """Lines 120-121: News safety filter rejection"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.NewsFilter.is_news_safe", return_value=False):
            result = await process_symbol("X", mock_data, [], AsyncMock(), {})
            assert result is None

@pytest.mark.asyncio
async def test_adr_exhausted_true(mock_data):
    """Line 137: ADR exhausted branch"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.IndicatorCalculator.calculate_adr", return_value=0.01):  # Small ADR
            with patch("main.IndicatorCalculator.get_asian_range", return_value=None):
                with patch("main.ScoringEngine.calculate_score", return_value=10.0):
                    with patch("main.MIN_CONFIDENCE_SCORE", 0):
                        with patch("main.EntryLogic.calculate_levels", return_value={'sl': 1.0, 'tp0': 1.2, 'tp1': 1.3, 'tp2': 1.4}):
                            with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 1.0, 'pips': 10, 'warning': ''}):
                                with patch("main.RiskManager.calculate_layers", return_value=[]):
                                    # Bullish H1 Trend
                                    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('close')] = 1.1
                                    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('ema_100')] = 1.0
                                    
                                    # Trigger sweep
                                    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('low')] = 0.99
                                    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('close')] = 1.01
                                    mock_data['m15'].iloc[-2, mock_data['m15'].columns.get_loc('low')] = 1.00
                                    
                                    result = await process_symbol("EURUSD=X", mock_data, [], AsyncMock(), {})
                                    assert result is not None
                                    assert result['adr_exhausted'] is True

@pytest.mark.asyncio
async def test_asian_sweep_buy(mock_data):
    """Line 152: Asian BUY sweep detection"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.IndicatorCalculator.calculate_adr", return_value=1.0):
            with patch("main.IndicatorCalculator.get_asian_range", return_value={'high': 1.1, 'low': 1.0}):
                with patch("main.ScoringEngine.calculate_score", return_value=10.0):
                    with patch("main.MIN_CONFIDENCE_SCORE", 0):
                        with patch("main.EntryLogic.calculate_levels", return_value={'sl': 1.0, 'tp0': 1.2, 'tp1': 1.3, 'tp2': 1.4}):
                            with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 1.0, 'pips': 10, 'warning': ''}):
                                with patch("main.RiskManager.calculate_layers", return_value=[]):
                                    # Bullish H1 Trend
                                    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('close')] = 1.1
                                    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('ema_100')] = 1.0
                                    
                                    # Trigger sweep on M15
                                    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('low')] = 0.99
                                    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('close')] = 1.01
                                    mock_data['m15'].iloc[-2, mock_data['m15'].columns.get_loc('low')] = 1.00
                                    
                                    # Trigger asian sweep on M5 (line 151)
                                    mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('low')] = 0.95
                                    
                                    result = await process_symbol("EURUSD=X", mock_data, [], AsyncMock(), {})
                                    assert result is not None
                                    assert result['asian_sweep'] is True

@pytest.mark.asyncio
async def test_asian_sweep_sell(mock_data):
    """Line 154: Asian SELL sweep detection"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.IndicatorCalculator.calculate_adr", return_value=1.0):
            with patch("main.IndicatorCalculator.get_asian_range", return_value={'high': 1.1, 'low': 1.0}):
                with patch("main.ScoringEngine.calculate_score", return_value=10.0):
                    with patch("main.MIN_CONFIDENCE_SCORE", 0):
                        with patch("main.EntryLogic.calculate_levels", return_value={'sl': 1.0, 'tp0': 1.2, 'tp1': 1.3, 'tp2': 1.4}):
                            with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 1.0, 'pips': 10, 'warning': ''}):
                                with patch("main.RiskManager.calculate_layers", return_value=[]):
                                    # Bearish H1
                                    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('close')] = 0.9
                                    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('ema_100')] = 1.0
                                    
                                    # SELL sweep on M15
                                    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('high')] = 1.15
                                    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('close')] = 1.09
                                    mock_data['m15'].iloc[-2, mock_data['m15'].columns.get_loc('high')] = 1.10
                                    
                                    # Trigger asian sweep on M5 (line 153)
                                    mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('high')] = 1.15
                                    
                                    result = await process_symbol("EURUSD=X", mock_data, [], AsyncMock(), {})
                                    assert result is not None
                                    assert result['asian_sweep'] is True

@pytest.mark.asyncio
async def test_ai_rejection(mock_data):
    """Lines 201-202: AI validation rejection"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.IndicatorCalculator.calculate_adr", return_value=1.0):
            with patch("main.ScoringEngine.calculate_score", return_value=9.5):
                ai_mock = AsyncMock()
                ai_mock.validate_signal.return_value = {'valid': False, 'institutional_logic': 'Rejected'}
                result = await process_symbol("X", mock_data, [], ai_mock, {})
                assert result is None

@pytest.mark.asyncio
async def test_dxy_sell_confluence(mock_data):
    """Line 236: DXY SELL+BULLISH confluence"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.IndicatorCalculator.calculate_adr", return_value=1.0):
            with patch("main.ScoringEngine.calculate_score", return_value=10.0):
                with patch("main.MIN_CONFIDENCE_SCORE", 0):
                    with patch("main.EntryLogic.calculate_levels", return_value={'sl': 1.0, 'tp0': 1.2, 'tp1': 1.3, 'tp2': 1.4}):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 1.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                dxy_df = pd.DataFrame({'close': [101], 'ema_100': [100]}, index=[pd.Timestamp.now(tz="UTC")])
                                data_batch = {'GC=F': mock_data, 'DXY': dxy_df}
                                
                                # SELL condition for Gold
                                mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('close')] = 1.0
                                mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('ema_100')] = 1.1
                                mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('high')] = 1.11
                                mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('close')] = 1.09
                                mock_data['m15'].iloc[-2, mock_data['m15'].columns.get_loc('high')] = 1.10
                                
                                result = await process_symbol("GC=F", mock_data, [], AsyncMock(), data_batch)
                                assert result is not None
                                assert "strength" in result['confluence']

@pytest.mark.asyncio
async def test_dxy_divergence(mock_data):
    """Line 238: DXY divergence"""
    with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
        with patch("main.IndicatorCalculator.calculate_adr", return_value=1.0):
            with patch("main.ScoringEngine.calculate_score", return_value=10.0):
                with patch("main.MIN_CONFIDENCE_SCORE", 0):
                    with patch("main.EntryLogic.calculate_levels", return_value={'sl': 1.0, 'tp0': 1.2, 'tp1': 1.3, 'tp2': 1.4}):
                        with patch("main.RiskManager.calculate_lot_size", return_value={'lots': 0.01, 'risk_cash': 1.0, 'risk_percent': 1.0, 'pips': 10, 'warning': ''}):
                            with patch("main.RiskManager.calculate_layers", return_value=[]):
                                # Bullish H1 Trend for Gold
                                mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('close')] = 1.1
                                mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('ema_100')] = 1.0
                                
                                dxy_df = pd.DataFrame({'close': [101], 'ema_100': [100]}, index=[pd.Timestamp.now(tz="UTC")])
                                data_batch = {'GC=F': mock_data, 'DXY': dxy_df}
                                
                                # SELL sweep on M15 (to trigger direction check, though we want BUY here)
                                # Wait, we want BUY Gold + BULLISH DXY = Divergence
                                mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('low')] = 0.99
                                mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('close')] = 1.01
                                mock_data['m15'].iloc[-2, mock_data['m15'].columns.get_loc('low')] = 1.00
                                
                                # Trigger asian sweep on M5
                                mock_data['m5'] = mock_data['m15'].copy()
                                mock_data['m5'].iloc[-1, mock_data['m5'].columns.get_loc('low')] = 0.95
                                
                                with patch("main.IndicatorCalculator.get_asian_range", return_value={'high': 1.1, 'low': 1.0}):
                                    result = await process_symbol("GC=F", mock_data, [], AsyncMock(), data_batch)
                                    assert result is not None
                                    assert "Divergence" in result['confluence']

# ========== main() Loop Tests ==========

@pytest.mark.asyncio
async def test_main_local_branding():
    """Lines 315-316: Local mode branding"""
    with patch("main.os.getenv", return_value="false"):
        with patch("main.DataFetcher.get_latest_data", side_effect=BreakLoop()):
            with pytest.raises(BreakLoop):
                await main()

@pytest.mark.asyncio
async def test_main_deduplication():
    """Lines 324-327: Deduplication logic in local mode"""
    timestamp = pd.Timestamp.now()
    market_data = {'EURUSD=X': {'m5': pd.DataFrame({'close': [1.1]}, index=[timestamp])}}
    
    with patch("main.os.getenv", return_value="false"):
        with patch("main.DataFetcher.get_latest_data", return_value=market_data):
            with patch("main.process_symbol", return_value=None):
                with patch("main.asyncio.sleep", side_effect=[None, BreakLoop()]):
                    with pytest.raises(BreakLoop):
                        await main()

@pytest.mark.asyncio
async def test_main_empty_tasks_continue():
    """Lines 332-334: Empty tasks handling in local mode"""
    with patch("main.os.getenv", return_value="false"):
        with patch("main.DataFetcher.get_latest_data", return_value={'DXY': {'m5': pd.DataFrame({'close': [1.1]}, index=[pd.Timestamp.now()])}}):
            with patch("main.asyncio.sleep", side_effect=BreakLoop()):
                with pytest.raises(BreakLoop):
                    await main()

@pytest.mark.asyncio
async def test_renderer_success():
    """Lines 347-348: Successful chart rendering"""
    signal = {'symbol': 'X', 'direction': 'BUY', 'confidence': 9.0, 'pair': 'X'}
    with patch("main.os.getenv", side_effect=lambda k, d=None: "true" if k == "GITHUB_ACTIONS" else d):
        with patch("main.DataFetcher.get_latest_data", return_value={'X': {'m5': pd.DataFrame({'close': [1.1]}, index=[pd.Timestamp.now()])}}):
            with patch("main.process_symbol", return_value=signal):
                with patch("main.CorrelationAnalyzer.filter_signals", return_value=[signal]):
                    mock_tel = AsyncMock()
                    mock_tel.format_signal.return_value = "msg"
                    with patch("main.TelegramService", return_value=mock_tel):
                        mock_rend = AsyncMock()
                        mock_rend.render_chart.return_value = b"chart"
                        with patch("main.TVChartRenderer", return_value=mock_rend):
                            with patch("main.SignalJournal", return_value=MagicMock()):
                                with patch("main.NewsFetcher.fetch_news", return_value=[]):
                                    await main()
                                    mock_tel.send_chart.assert_called()

@pytest.mark.asyncio
async def test_main_import():
    """Line 370: Main entry point"""
    import main as m
    assert hasattr(m, 'main')
    assert callable(m.main)
