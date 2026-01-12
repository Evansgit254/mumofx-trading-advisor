import asyncio
import pandas as pd
from datetime import datetime, timedelta
from strategies.smc_strategy import SMCStrategy
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from config.config import SYMBOLS, DXY_SYMBOL, TNX_SYMBOL

async def debug_smc():
    print("🔍 DEBUGGING SMC SIGNAL FLOW")
    smc = SMCStrategy()
    symbol = "EURUSD=X"
    # Fetch 10 days to allow for EMA 100 on H1
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Fetching data for {symbol}...")
    h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
    m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
    m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
    h4 = DataFetcher.fetch_range(symbol, "4h", start=start_date, end=end_date)
    
    # Macro context
    dxy = DataFetcher.fetch_range(DXY_SYMBOL, "1h", start=start_date, end=end_date)
    tnx = DataFetcher.fetch_range(TNX_SYMBOL, "1h", start=start_date, end=end_date)
    
    h1 = IndicatorCalculator.add_indicators(h1, "h1")
    m15 = IndicatorCalculator.add_indicators(m15, "m15")
    m5 = IndicatorCalculator.add_indicators(m5, "m5")
    h4 = IndicatorCalculator.add_indicators(h4, "h4")
    dxy = IndicatorCalculator.add_indicators(dxy, "h1")
    tnx = IndicatorCalculator.add_indicators(tnx, "h1")
    
    market_context = {'DXY': dxy, '^TNX': tnx}
    
    # Run SMC at each M5 step for the last day
    steps = 288 # last 24 hours
    found = 0
    for i in range(len(m5) - steps, len(m5)):
        t = m5.index[i]
        curr_m5 = m5.iloc[:i+1]
        curr_m15 = m15[m15.index <= t]
        curr_h1 = h1[h1.index <= t]
        curr_h4 = h4[h4.index <= t]
        
        signal = await smc.analyze(symbol, {
            'h1': curr_h1,
            'm15': curr_m15,
            'm5': curr_m5,
            'h4': curr_h4
        }, [], market_context)
        
        if signal:
            print(f"🎯 SMC SIGNAL FOUND at {t}: {signal['direction']} | Score: {signal['confidence']}")
            found += 1
            
    print(f"Debug finished. Signals found: {found}")

if __name__ == "__main__":
    asyncio.run(debug_smc())
