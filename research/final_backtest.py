import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND, EMA_FAST, EMA_SLOW, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.session_filter import SessionFilter

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_final_backtest(days=30):
    print(f"🚀 FINAL OPTIMIZED BACKTEST (Last {days} days)")
    print(f"Config: EMA_Trend={EMA_TREND}, ATR_Mult={ATR_MULTIPLIER}, Score>={MIN_CONFIDENCE_SCORE}")
    print(f"ML Filter: {'ACTIVE' if ML_MODEL else 'INACTIVE'}")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    total_wins = 0
    total_losses = 0
    ml_rejected = 0
    
    for symbol in SYMBOLS:
        print(f"\nScanning {symbol}...")
        h1_df = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15_df = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5_df = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if any(df is None or df.empty for df in [h1_df, m15_df, m5_df]): continue
            
        h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
        m15_df = IndicatorCalculator.add_indicators(m15_df, "15m")
        m5_df = IndicatorCalculator.add_indicators(m5_df, "5m")
        
        symbol_results = []
        idx = 100
        while idx < len(m15_df):
            t = m15_df.index[idx]
            latest_m15 = m15_df.iloc[idx]
            
            # H1 Trend
            state_h1 = h1_df[h1_df.index <= t]
            if state_h1.empty: idx += 1; continue
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            
            # M15 Sweep
            state_m15 = m15_df.iloc[:idx+1]
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            # Ensure valid session (London Open or Extended NY)
            if not SessionFilter.is_valid_session(t):
                idx += 1
                continue

            direction = None
            sweep_level = None
            if h1_trend_val == 1 and latest_m15['low'] < prev_low < latest_m15['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend_val == -1 and latest_m15['high'] > prev_high > latest_m15['close']:
                direction = "SELL"; sweep_level = prev_high
                
            if not direction: idx += 1; continue
            
            # Scoring
            displaced = DisplacementAnalyzer.is_displaced(state_m15, direction)
            score = ScoringEngine.calculate_score({
                'h1_aligned': True,
                'sweep_type': 'M15_SWEEP',
                'displaced': displaced,
                'pullback': True,
                'volatile': True
            })
            
            if score < MIN_CONFIDENCE_SCORE: idx += 1; continue
            
            # ML Filter
            if ML_MODEL:
                body_ratio = abs(latest_m15['close'] - latest_m15['open']) / (latest_m15['high'] - latest_m15['low']) if (latest_m15['high'] - latest_m15['low']) else 0
                features = [[latest_m15['rsi'], body_ratio, latest_m15['atr']/latest_m15['close'], 1 if displaced else 0, h1_trend_val]]
                prob = ML_MODEL.predict_proba(features)[0][1]
                
                if prob < 0.40: # Conservative ML threshold
                    ml_rejected += 1
                    idx += 24
                    continue

            # Outcome (M5)
            levels = EntryLogic.calculate_levels(state_m15, direction, sweep_level, latest_m15['atr'])
            m5_start = m5_df.index.get_indexer([t], method='nearest')[0]
            
            hit = None
            for j in range(m5_start + 1, min(m5_start + 288, len(m5_df))):
                fut = m5_df.iloc[j]
                if direction == "BUY":
                    if fut['low'] <= levels['sl']: hit = "LOSS"; break
                    if fut['high'] >= levels['tp2']: hit = "WIN"; break
                else:
                    if fut['high'] >= levels['sl']: hit = "LOSS"; break
                    if fut['low'] <= levels['tp2']: hit = "WIN"; break
            
            if hit:
                symbol_results.append(hit)
                idx += 24
            else:
                idx += 1
                
        if symbol_results:
            w = symbol_results.count("WIN")
            l = symbol_results.count("LOSS")
            wr = (w/(w+l))*100
            print(f"✔️ {symbol}: {w+l} trades | {w}W - {l}L | WR: {wr:.1f}%")
            total_wins += w
            total_losses += l
            
    print("\n" + "═"*40)
    print(f"🏁 FINAL RESULTS")
    print(f"Total Trades: {total_wins + total_losses}")
    print(f"ML Rejected: {ml_rejected}")
    win_rate = (total_wins / (total_wins + total_losses)) * 100 if (total_wins + total_losses) > 0 else 0
    print(f"Optimized Win Rate: {win_rate:.1f}%")
    print("═"*40)

if __name__ == "__main__":
    asyncio.run(run_final_backtest(30))
