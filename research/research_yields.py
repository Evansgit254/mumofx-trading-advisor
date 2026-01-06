import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import EMA_TREND
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator

async def research_yield_correlation():
    start = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    # Symbols to test
    target_symbols = ["GC=F", "EURUSD=X", "GBPUSD=X"]
    yield_symbol = "^TNX"
    
    print(f"🔬 Researching Yield Correlation from {start} to {end}...")
    
    yield_df = DataFetcher.fetch_range(yield_symbol, "1h", start, end)
    if yield_df is None or yield_df.empty: return
    yield_df.index = yield_df.index.tz_convert("UTC").tz_localize(None)
    yield_df = yield_df.sort_index()
    
    results = []
    
    for symbol in target_symbols:
        market_df = DataFetcher.fetch_range(symbol, "1h", start, end)
        if market_df is None or market_df.empty: continue
        
        market_df.index = market_df.index.tz_convert("UTC").tz_localize(None)
        market_df = market_df.sort_index()
        
        # Inter-market analysis
        # We want to see if Market Close(t) - Close(t-1) correlates with Yield Close(t) - Close(t-1)
        merged = pd.merge_asof(
            market_df[['close']].rename(columns={'close': 'market_close'}), 
            yield_df[['close']].rename(columns={'close': 'yield_close'}),
            left_index=True, right_index=True
        )
        
        merged['market_ret'] = merged['market_close'].pct_change()
        merged['yield_ret'] = merged['yield_close'].pct_change()
        
        correlation = merged['market_ret'].corr(merged['yield_ret'])
        print(f"📊 {symbol} vs Treasury Yield Correlation: {correlation:.3f}")
        
        # Check specifically for "Inverse Outliers"
        # For Gold (GC=F), we expect strong INVERSE correlation
        if symbol == "GC=F":
            outliers = merged[(merged['market_ret'] > 0) & (merged['yield_ret'] > 0)].count()
            print(f"⚠️ {symbol} Divergence Count (Both Up): {outliers['market_ret']} bars")

if __name__ == "__main__":
    asyncio.run(research_yield_correlation())
