import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND, EMA_FAST, EMA_SLOW
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def collect_training_data(days=50):
    logger.info(f"📊 Building training dataset for last {days} days...")
    dataset = []
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    for symbol in SYMBOLS:
        logger.info(f"  Processing {symbol}...")
        h1_df = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15_df = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5_df = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if any(df is None or df.empty for df in [h1_df, m15_df, m5_df]):
            continue
            
        h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
        m15_df = IndicatorCalculator.add_indicators(m15_df, "15m")
        m5_df = IndicatorCalculator.add_indicators(m5_df, "5m")
        
        idx = 100
        while idx < len(m15_df):
            t = m15_df.index[idx]
            latest_m15 = m15_df.iloc[idx]
            
            # 1. H1 Narrative
            state_h1 = h1_df[h1_df.index <= t]
            if state_h1.empty: 
                idx += 1
                continue
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            
            # 2. Potential Sweep
            state_m15 = m15_df.iloc[:idx+1]
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend_val == 1 and latest_m15['low'] < prev_low and latest_m15['close'] > prev_low:
                direction = "BUY"
                sweep_level = prev_low
            elif h1_trend_val == -1 and latest_m15['high'] > prev_high and latest_m15['close'] < prev_high:
                direction = "SELL"
                sweep_level = prev_high
                
            if not direction:
                idx += 1
                continue

            # 3. Capture Technical Features
            rsi = latest_m15['rsi']
            body_ratio = abs(latest_m15['close'] - latest_m15['open']) / (latest_m15['high'] - latest_m15['low']) if (latest_m15['high'] - latest_m15['low']) != 0 else 0
            atr_norm = latest_m15['atr'] / latest_m15['close']
            displaced = 1 if DisplacementAnalyzer.is_displaced(state_m15, direction) else 0
            
            # 4. Levels & Outcome
            atr = latest_m15['atr']
            levels = EntryLogic.calculate_levels(state_m15, direction, sweep_level, atr)
            
            win_loss = 0 # Loss
            m5_start_idx = m5_df.index.get_indexer([t], method='nearest')[0]
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                future_bar = m5_df.iloc[j]
                if direction == "BUY":
                    if future_bar['low'] <= levels['sl']: break
                    if future_bar['high'] >= levels['tp2']: win_loss = 1; break
                else:
                    if future_bar['high'] >= levels['sl']: break
                    if future_bar['low'] <= levels['tp2']: win_loss = 1; break
            
            dataset.append({
                'symbol': symbol,
                'rsi': rsi,
                'body_ratio': body_ratio,
                'atr_norm': atr_norm,
                'displaced': displaced,
                'h1_trend': h1_trend_val,
                'outcome': win_loss
            })
            idx += 24 # Avoid overlapping setups for training purity

    df_out = pd.DataFrame(dataset)
    df_out.to_csv("training/historical_data.csv", index=False)
    logger.info(f"✅ Training data saved! ({len(df_out)} samples)")

if __name__ == "__main__":
    asyncio.run(collect_training_data(days=50))
