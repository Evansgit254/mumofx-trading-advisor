import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.scoring import ScoringEngine

async def check_daily_frequency():
    # Last 30 days
    start = (datetime.now() - timedelta(days=32)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    # Expanded symbols for intraday consistency
    EXPANDED_SYMBOLS = SYMBOLS + ["USDCAD=X", "NZDUSD=X", "^GSPC", "^IXIC"]
    
    thresholds = [8.5, 8.7, 9.0]
    results = {t: set() for t in thresholds}
    
    print(f"📊 Analyzing Signal Frequency ({len(EXPANDED_SYMBOLS)} Pairs) from {start} to {end}...")
    
    for symbol in EXPANDED_SYMBOLS:
        h1_df = DataFetcher.fetch_range(symbol, "1h", start=start, end=end)
        m15_df = DataFetcher.fetch_range(symbol, "15m", start=start, end=end)
        
        if h1_df is None or m15_df is None or h1_df.empty or m15_df.empty: continue
        
        h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
        m15_df = IndicatorCalculator.add_indicators(m15_df, "15m")
        
        idx = 100
        while idx < len(m15_df):
            t = m15_df.index[idx]
            latest_m15 = m15_df.iloc[idx]
            
            # Narrative (using optimized EMA_TREND)
            state_h1 = h1_df[h1_df.index <= t]
            if state_h1.empty: 
                idx += 1
                continue
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            h1_trend = "BULLISH" if h1_trend_val == 1 else "BEARISH"
            
            # Setup
            state_m15 = m15_df.iloc[:idx+1]
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            if h1_trend == "BULLISH" and latest_m15['low'] < prev_low < latest_m15['close']: direction = "BUY"
            elif h1_trend == "BEARISH" and latest_m15['high'] > prev_high > latest_m15['close']: direction = "SELL"
            
            if not direction:
                idx += 1
                continue
                
            # Scoring (Simulated high-quality components)
            score_details = {
                'h1_aligned': True,
                'sweep_type': 'M15_SWEEP',
                'displaced': True,
                'pullback': True,
                'volatile': True
            }
            score = ScoringEngine.calculate_score(score_details)
            
            day_key = t.strftime("%Y-%m-%d")
            # Only count weekdays (Mon-Fri)
            if t.weekday() < 5:
                for t_val in thresholds:
                    if score >= t_val:
                        results[t_val].add(day_key)
            
            idx += 24 # Skip cluster
            
    print("\n🏁 FREQUENCY RESULTS (Unique Trading Days with at least 1 Signal):")
    total_trading_days = 22 # Monthly average
    for t_val, days in results.items():
        count = len(days)
        pct = (count / total_trading_days) * 100
        print(f"Confidence {t_val}+: {count}/{total_trading_days} days ({min(100, pct):.1f}%) | Signals per month: ~{count}")

if __name__ == "__main__":
    asyncio.run(check_daily_frequency())
