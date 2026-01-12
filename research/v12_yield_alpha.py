import asyncio
import pandas as pd
from datetime import datetime, timedelta
from data.fetcher import DataFetcher

async def v12_research_yield_alpha():
    days = 30
    now = datetime.now()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    
    symbols = ["GC=F", "EURUSD=X", "GBPUSD=X"]
    yield_sym = "^TNX"
    
    print(f"🔬 Intensifying Research: Cross-Asset Yield Correlation ({days} days)...")
    
    y_df = DataFetcher.fetch_range(yield_sym, "1h", start, end)
    if y_df is None: return
    
    # Calculate Yield Trend (10-period EMA on H1)
    y_df['yield_ema'] = y_df['close'].ewm(span=10).mean()
    y_df['yield_trend'] = y_df['close'] > y_df['yield_ema']
    
    for symbol in symbols:
        m_df = DataFetcher.fetch_range(symbol, "1h", start, end)
        if m_df is None: continue
        
        # Merge Yield data
        merged = pd.merge_asof(
            m_df[['close']].rename(columns={'close': 'm_close'}),
            y_df[['yield_trend', 'close']].rename(columns={'close': 'y_close'}),
            left_index=True, right_index=True
        )
        
        # Calculate Forward Returns
        merged['fwd_ret'] = merged['m_close'].shift(-4) - merged['m_close'] # 4-hour outlook
        
        # Test: If Yield is falling (yield_trend=False), Gold (GC=F) should go UP
        if symbol == "GC=F":
            bullish_yield = merged[merged['yield_trend'] == False]
            win_rate = (bullish_yield['fwd_ret'] > 0).mean()
            print(f"🥇 Gold Upside Prob when Yields FALL: {win_rate*100:.1f}%")
        else:
            # USD pairs vs Yields
            bearish_yield = merged[merged['yield_trend'] == True]
            win_rate = (bearish_yield['fwd_ret'] < 0).mean() # Yield up, USD up, Pair DOWN
            print(f"💵 {symbol} Downside Prob when Yields RISE: {win_rate*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(v12_research_yield_alpha())
