import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator

async def run_optimization():
    print("📈 Starting Parameter Optimization Sweep...")
    
    # Ranges to test
    trend_emas = [100, 200]
    atr_multipliers = [1.5, 2.0, 2.5]
    
    results = []
    
    # We'll use a smaller set of data for optimization speed
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    for trend_ema in trend_emas:
        for atr_mult in atr_multipliers:
            print(f"  Testing: TrendEMA={trend_ema}, ATR_Mult={atr_mult}")
            
            total_profit = 0
            wins = 0
            total_trades = 0
            
            for symbol in SYMBOLS:
                h1_df = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
                m15_df = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
                m5_df = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
                
                if any(df is None or df.empty for df in [h1_df, m15_df, m5_df]): continue
                
                h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
                # Custom trend EMA for testing
                h1_df['test_ema'] = h1_df['close'].ewm(span=trend_ema, adjust=False).mean()
                
                m15_df = IndicatorCalculator.add_indicators(m15_df, "15m")
                m5_df = IndicatorCalculator.add_indicators(m5_df, "5m")
                
                idx = 50
                while idx < len(m15_df):
                    t = m15_df.index[idx]
                    latest_m15 = m15_df.iloc[idx]
                    
                    state_h1 = h1_df[h1_df.index <= t]
                    if state_h1.empty: idx += 1; continue
                    
                    trend = "BULL" if state_h1.iloc[-1]['close'] > state_h1.iloc[-1]['test_ema'] else "BEAR"
                    
                    # Sweep Detection (approx)
                    state_m15 = m15_df.iloc[:idx+1]
                    prev_low = state_m15.iloc[-21:-1]['low'].min()
                    prev_high = state_m15.iloc[-21:-1]['high'].max()
                    
                    if trend == "BULL" and latest_m15['low'] < prev_low < latest_m15['close']:
                        # Simulated BUY
                        sl = prev_low - (latest_m15['atr'] * 0.5)
                        tp = latest_m15['close'] + (latest_m15['atr'] * atr_mult)
                        
                        m5_start = m5_df.index.get_indexer([t], method='nearest')[0]
                        for j in range(m5_start+1, min(m5_start+200, len(m5_df))):
                            fut = m5_df.iloc[j]
                            if fut['low'] <= sl: total_profit -= 1; total_trades += 1; break
                            if fut['high'] >= tp: total_profit += atr_mult; wins += 1; total_trades += 1; break
                        idx += 20
                    elif trend == "BEAR" and latest_m15['high'] > prev_high > latest_m15['close']:
                        # Simulated SELL
                        sl = prev_high + (latest_m15['atr'] * 0.5)
                        tp = latest_m15['close'] - (latest_m15['atr'] * atr_mult)
                        
                        m5_start = m5_df.index.get_indexer([t], method='nearest')[0]
                        for j in range(m5_start+1, min(m5_start+200, len(m5_df))):
                            fut = m5_df.iloc[j]
                            if fut['high'] >= sl: total_profit -= 1; total_trades += 1; break
                            if fut['low'] <= tp: total_profit += atr_mult; wins += 1; total_trades += 1; break
                        idx += 20
                    else:
                        idx += 1
            
            results.append({
                'trend_ema': trend_ema,
                'atr_mult': atr_mult,
                'total_profit': total_profit,
                'win_rate': (wins/total_trades*100) if total_trades > 0 else 0,
                'trades': total_trades
            })

    results_df = pd.DataFrame(results)
    best = results_df.sort_values(by='total_profit', ascending=False).iloc[0]
    print(f"\n🏆 BEST SETTINGS FOUND:")
    print(best)
    results_df.to_csv("training/optimization_results.csv", index=False)

if __name__ == "__main__":
    asyncio.run(run_optimization())
