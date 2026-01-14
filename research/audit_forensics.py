import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta, time
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.correlation import CorrelationAnalyzer

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_forensic_audit(days=60):
    print(f"🕵️ FORENSIC LOSS AUDIT (Last {days} days)")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("Fetching data...")
    for symbol in SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if all(df is not None and not df.empty for df in [h1, m15, m5]):
            all_data[symbol] = {
                'h1': IndicatorCalculator.add_indicators(h1, "h1"),
                'm15': IndicatorCalculator.add_indicators(m15, "15m"),
                'm5': IndicatorCalculator.add_indicators(m5, "5m")
            }
            valid_symbols.append(symbol)
    
    if not valid_symbols: return

    timeline = all_data[valid_symbols[0]]['m15'].index
    forensic_records = []
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    print(f"Simulating {len(timeline)} bars...")
    
    for t in timeline:
        potential_batch = []
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            m15_df = all_data[symbol]['m15']
            if t not in m15_df.index: continue
            idx = m15_df.index.get_loc(t)
            if idx < 100: continue
            
            latest_m5 = all_data[symbol]['m5'][all_data[symbol]['m5'].index <= t].iloc[-1]
            latest_m15 = m15_df.iloc[idx]
            state_m15 = m15_df.iloc[:idx+1]
            state_h1 = all_data[symbol]['h1'][all_data[symbol]['h1'].index <= t]
            if state_h1.empty: continue
            
            # ADR Utilization
            adr_series = IndicatorCalculator.calculate_adr(state_h1)
            adr = adr_series.iloc[-1] if not adr_series.empty else 0
            
            today_data = state_h1[state_h1.index.date == t.date()]
            current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
            adr_util = (current_range / adr) if adr > 0 else 0
            
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            
            # Sweep Logic
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend_val == 1 and latest_m15['low'] < prev_low < latest_m15['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend_val == -1 and latest_m15['high'] > prev_high > latest_m15['close']:
                direction = "SELL"; sweep_level = prev_high
            
            if not direction: continue
            
            # Quality Checks
            # Asian Range
            ar_df = IndicatorCalculator.calculate_asian_range(state_m15)
            asian_sweep = False
            asian_quality = False
            
            if not ar_df.empty:
                latest_ar = ar_df.iloc[-1]
                raw_range = latest_ar['asian_high'] - latest_ar['asian_low']
                pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
                if pips >= ASIAN_RANGE_MIN_PIPS: asian_quality = True
                if direction == "BUY" and latest_m5['low'] < latest_ar['asian_low']: asian_sweep = True
                elif direction == "SELL" and latest_m5['high'] > latest_ar['asian_high']: asian_sweep = True

            poc = IndicatorCalculator.calculate_poc(all_data[symbol]['m5'][all_data[symbol]['m5'].index <= t])
            atr = latest_m5['atr']
            at_value = abs(latest_m5['close'] - poc) <= (0.5 * atr)

            score_details = {
                'h1_aligned': True,
                'sweep_type': 'M15_SWEEP',
                'displaced': DisplacementAnalyzer.is_displaced(state_m15, direction),
                'pullback': True,
                'volatile': latest_m5['atr'] > all_data[symbol]['m5'].iloc[:all_data[symbol]['m5'].index.get_loc(latest_m5.name)]['atr'].tail(50).mean(),
                'asian_sweep': asian_sweep,
                'asian_quality': asian_quality,
                'adr_exhausted': adr_util >= ADR_THRESHOLD_PERCENT,
                'at_value': at_value
            }
            confidence = ScoringEngine.calculate_score(score_details)
            if confidence < MIN_CONFIDENCE_SCORE: continue

            potential_batch.append({
                'symbol': symbol, 'pair': symbol.replace('=X','').replace('^',''),
                'direction': direction, 't': t, 'sweep_level': sweep_level,
                'atr': atr, 'confidence': confidence, 'adr_util': adr_util, 
                'asian_sweep': asian_sweep, 'at_value': at_value, 'h1_trend': h1_trend_val
            })

        if not potential_batch: continue
        filtered = CorrelationAnalyzer.filter_signals(potential_batch)
        
        for sig in filtered:
            symbol = sig['symbol']
            m5_df = all_data[symbol]['m5']
            levels = EntryLogic.calculate_levels(m5_df[m5_df.index <= sig['t']], sig['direction'], sig['sweep_level'], sig['atr'])
            
            m5_start_idx = m5_df.index.get_indexer([sig['t']], method='nearest')[0]
            
            outcome = "IN_PROGRESS"
            max_favorable = 0
            duration = 0
            
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                fut = m5_df.iloc[j]
                duration += 5 # minutes
                
                # Track max favorable move
                if sig['direction'] == "BUY":
                    move = (fut['high'] - levels['sl']) / (levels['tp2'] - levels['sl']) if (levels['tp2'] - levels['sl']) else 0
                    max_favorable = max(max_favorable, move)
                    if fut['low'] <= levels['sl']: outcome = "LOSS"; break
                    if fut['high'] >= levels['tp2']: outcome = "WIN"; break
                else:
                    move = (levels['sl'] - fut['low']) / (levels['sl'] - levels['tp2']) if (levels['sl'] - levels['tp2']) else 0
                    max_favorable = max(max_favorable, move)
                    if fut['high'] >= levels['sl']: outcome = "LOSS"; break
                    if fut['low'] <= levels['tp2']: outcome = "WIN"; break

            # Categorize Loss
            loss_category = "N/A"
            if outcome == "LOSS":
                if max_favorable < 0.1: loss_category = "Instant Reversal" # Dropped immediately
                elif max_favorable > 0.8: loss_category = "Heartbreaker" # Almost hit TP then reversed
                elif duration > 120: loss_category = "Slow Bleed" # Chopped for >2 hours
                else: loss_category = "Standard Stop"

            forensic_records.append({
                'time': sig['t'], 'symbol': symbol, 'direction': sig['direction'],
                'outcome': outcome, 'loss_category': loss_category,
                'confidence': sig['confidence'], 'adr_util': sig['adr_util'],
                'asian_sweep': sig['asian_sweep'], 'at_value': sig['at_value'],
                'max_fav_ratio': round(max_favorable, 2), 'duration_mins': duration,
                'hour': sig['t'].hour
            })
            cooldowns[symbol] = t + timedelta(hours=6)

    df_forensic = pd.DataFrame(forensic_records)
    df_forensic.to_csv("audit_forensics.csv", index=False)
    print(f"\n✅ Audit Complete! {len(df_forensic)} trades captured.")
    print("\n📊 LOSS CATEGORY BREAKDOWN:")
    print(df_forensic[df_forensic['outcome'] == 'LOSS']['loss_category'].value_counts())
    
    print("\n⏰ TIME-OF-DAY LOSSES:")
    print(df_forensic[df_forensic['outcome'] == 'LOSS']['hour'].value_counts().sort_index())

if __name__ == "__main__":
    asyncio.run(run_forensic_audit(60))
