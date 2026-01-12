import asyncio
import pandas as pd
from datetime import datetime, timedelta
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.smc_strategy import SMCStrategy
from filters.macro_filter import MacroFilter

async def debug_smc():
    symbol = "GC=F"
    days = 10
    now = datetime.now()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🕵️ Debugging SMC for {symbol}...")
    
    h1 = DataFetcher.fetch_range(symbol, "1h", start, end)
    m15 = DataFetcher.fetch_range(symbol, "15m", start, end)
    m5 = DataFetcher.fetch_range(symbol, "5m", start, end)
    h4 = DataFetcher.fetch_range(symbol, "4h", start, end)
    
    if any(df is None for df in [h1, m15, m5, h4]):
        print("Data fetch failed")
        return
        
    data = {
        'h1': IndicatorCalculator.add_indicators(h1, "h1"),
        'm15': IndicatorCalculator.add_indicators(m15, "15m"),
        'm5': IndicatorCalculator.add_indicators(m5, "5m"),
        'h4': IndicatorCalculator.add_indicators(h4, "4h")
    }
    
    # Macro context
    dxy_debug = DataFetcher.fetch_range("DX-Y.NYB", "1h", start, end)
    tnx_debug = DataFetcher.fetch_range("^TNX", "1h", start, end)
    
    macro_context = {
        'DXY': IndicatorCalculator.add_indicators(dxy_debug, "h1") if dxy_debug is not None else None,
        '^TNX': IndicatorCalculator.add_indicators(tnx_debug, "h1") if tnx_debug is not None else None
    }
    
    strategy = SMCStrategy()
    
    # Simulate last 100 M5 bars
    for i in range(100, 0, -1):
        t = m5.index[-i]
        subset = {
            'h1': data['h1'][data['h1'].index <= t],
            'm15': data['m15'][data['m15'].index <= t],
            'm5': data['m5'][data['m5'].index <= t],
            'h4': data['h4'][data['h4'].index <= t]
        }
        
        # Prepare Temporal Macro Context
        m_context = {}
        if macro_context['DXY'] is not None:
            m_context['DXY'] = macro_context['DXY'][macro_context['DXY'].index <= t]
        if macro_context['^TNX'] is not None:
            m_context['^TNX'] = macro_context['^TNX'][macro_context['^TNX'].index <= t]
            
        # Check Direction manually
        m5_sub = subset['m5']
        h1_sub = subset['h1']
        h1_ema = h1_sub.iloc[-1]['ema_100']
        h1_trend = "BULLISH" if h1_sub.iloc[-1]['close'] > h1_ema else "BEARISH"
        
        prev_low = m5_sub['low'].iloc[-51:-1].min()
        latest_low = m5_sub['low'].iloc[-1]
        latest_close = m5_sub['close'].iloc[-1]
        
        sweep = latest_low < prev_low and latest_close > prev_low
        
        if sweep:
            print(f"[{t}] 🧹 Sweep Detected! Trend: {h1_trend} | Low: {latest_low} | PrevLow: {prev_low}")
            signal = await strategy.analyze(symbol, subset, [], m_context)
            if signal:
                print(f"[{t}] ✅ SIGNAL GENERATED: {signal['direction']} @ {signal['entry_price']}")
            else:
                print(f"[{t}] ❌ Signal Filtered Out.")

if __name__ == "__main__":
    asyncio.run(debug_smc())
