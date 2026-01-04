import asyncio
import pandas as pd
from datetime import datetime, timedelta, time
from data.fetcher import DataFetcher

async def research_asian_sweeps():
    start = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    symbols = ["EURUSD=X", "GBPUSD=X", "GC=F"]
    print(f"🔬 Researching Asian Range Sweeps from {start} to {end}...")
    
    for symbol in symbols:
        df = DataFetcher.fetch_range(symbol, "15m", start, end)
        if df is None or df.empty: continue
        
        # Define Asian Session: 00:00 - 08:00 UTC
        total_days = 0
        sweep_wins = 0
        
        # Group by day
        df['date'] = df.index.date
        for date, day_df in df.groupby('date'):
            asian_range = day_df[(day_df.index.time >= time(0, 0)) & (day_df.index.time < time(8, 0))]
            if asian_range.empty: continue
            
            asian_high = asian_range['high'].max()
            asian_low = asian_range['low'].min()
            
            # London/NY: 08:00 - 20:00 UTC
            power_hours = day_df[(day_df.index.time >= time(8, 0)) & (day_df.index.time < time(20, 0))]
            if power_hours.empty: continue
            
            # Check for sweep
            swept_high = (power_hours['high'] > asian_high).any()
            swept_low = (power_hours['low'] < asian_low).any()
            
            if swept_high or swept_low:
                total_days += 1
                # If it swept AND reversed (simple check: closed inside asian range later)
                if (power_hours.iloc[-1]['close'] < asian_high) and (power_hours.iloc[-1]['close'] > asian_low):
                    sweep_wins += 1
                    
        print(f"📊 {symbol} Asian Sweep Reversal Rate: {sweep_wins}/{total_days} ({ (sweep_wins/total_days*100) if total_days > 0 else 0:.1f}%)")

if __name__ == "__main__":
    asyncio.run(research_asian_sweeps())
