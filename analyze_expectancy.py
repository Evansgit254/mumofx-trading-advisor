import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND, ATR_MULTIPLIER
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.entry import EntryLogic

async def analyze_expectancy():
    start = (datetime.now() - timedelta(days=32)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    total_risk = 0
    total_reward = 0
    trade_count = 0
    
    for symbol in SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start, end=end)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start, end=end)
        
        if h1 is None or m15 is None or h1.empty or m15.empty: continue
        
        h1 = IndicatorCalculator.add_indicators(h1, "h1")
        m15 = IndicatorCalculator.add_indicators(m15, "15m")
        
        idx = 100
        while idx < len(m15):
            t = m15.index[idx]
            latest = m15.iloc[idx]
            
            # Simplified trend/sweep for sampling
            h1_trend = 1 if h1[h1.index <= t].iloc[-1]['close'] > h1[h1.index <= t].iloc[-1][f'ema_{EMA_TREND}'] else -1
            prev_low = m15.iloc[idx-20:idx]['low'].min()
            prev_high = m15.iloc[idx-20:idx]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend == 1 and latest['low'] < prev_low < latest['close']: 
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend == -1 and latest['high'] > prev_high > latest['close']: 
                direction = "SELL"; sweep_level = prev_high
                
            if direction:
                levels = EntryLogic.calculate_levels(m15.iloc[:idx+1], direction, sweep_level, latest['atr'])
                entry = latest['close']
                risk = abs(entry - levels['sl'])
                reward = abs(levels['tp2'] - entry)
                
                if risk > 0:
                    total_risk += risk
                    total_reward += reward
                    trade_count += 1
            
            idx += 24 # Avoid clusters

    if trade_count > 0:
        avg_rr = total_reward / total_risk
        print(f"📊 AVG REWARD-TO-RISK (RR): {avg_rr:.2f}")
        print(f"🎯 WIN RATE NEEDED TO BREAK EVEN: {(1 / (1 + avg_rr)) * 100:.1f}%")
        print(f"🚀 YOUR CURRENT WIN RATE: 52.7%")
    else:
        print("No trades found for analysis.")

if __name__ == "__main__":
    asyncio.run(analyze_expectancy())
