import pandas as pd
from main import process_symbol
from unittest.mock import AsyncMock, patch
from datetime import datetime

async def debug():
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
        'atr_avg': [0.01] * 100
    }, index=[timestamp - pd.Timedelta(minutes=5*i) for i in range(100)][::-1])
    mock_data = {
        'm5': df.copy(),
        'm15': df.copy(),
        'h1': df.copy()
    }
    
    # SELL Case trigger
    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('close')] = 1.0
    mock_data['h1'].iloc[-1, mock_data['h1'].columns.get_loc('ema_100')] = 1.1
    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('high')] = 1.11
    mock_data['m15'].iloc[-1, mock_data['m15'].columns.get_loc('close')] = 1.09
    
    with patch("main.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 17
        with patch("main.IndicatorCalculator.add_indicators", side_effect=lambda df, tf: df):
            with patch("main.MIN_CONFIDENCE_SCORE", 0):
                res = await process_symbol("EURUSD=X", mock_data, [], AsyncMock(), mock_data)
                print(f"RES: {res}")
                if res is None:
                    # Debug why
                    lookback = 50 # 17:00 NY
                    prev_high = mock_data['m15']['high'].iloc[-(lookback+1):-1].max()
                    latest_high = mock_data['m15']['high'].iloc[-1]
                    latest_close = mock_data['m15']['close'].iloc[-1]
                    h1_close = mock_data['h1'].iloc[-1]['close']
                    h1_ema = mock_data['h1'].iloc[-1]['ema_100']
                    print(f"lookback: {lookback}")
                    print(f"prev_high: {prev_high}")
                    print(f"latest_high: {latest_high}")
                    print(f"latest_close: {latest_close}")
                    print(f"h1_trend: {'BEARISH' if h1_close < h1_ema else 'BULLISH'}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug())
