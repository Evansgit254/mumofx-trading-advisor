import asyncio
import pandas as pd
import joblib
import os
import sys
from datetime import datetime, timedelta, time
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, GOLD_CONFIDENCE_THRESHOLD, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS, DXY_SYMBOL, INSTITUTIONAL_TF
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from strategy.imbalance import ImbalanceDetector
from strategy.crt import CRTAnalyzer
from filters.session_filter import SessionFilter

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_v8_backtest(days=30):
    print(f"🚀 V8.0 INSTITUTIONAL BACKTEST (Last {days} days)")
    print(f"Symbols: {SYMBOLS}")
    print(f"Institutional TF: {INSTITUTIONAL_TF}")
    print(f"CRT Validation: ACTIVE")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("Fetching data...")
    # Fetch DXY first
    dxy_h1 = DataFetcher.fetch_range(DXY_SYMBOL, "1h", start=start_date, end=end_date)
    if dxy_h1 is not None and not dxy_h1.empty:
        dxy_h1 = IndicatorCalculator.add_indicators(dxy_h1, "h1")
    
    for symbol in SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        h4 = DataFetcher.fetch_range(symbol, "4h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if all(df is not None and not df.empty for df in [h1, h4, m15, m5]):
            all_data[symbol] = {
                'h1': IndicatorCalculator.add_indicators(h1, "h1"),
                'h4': IndicatorCalculator.add_indicators(h4, "h4"),
                'm15': IndicatorCalculator.add_indicators(m15, "15m"),
                'm5': IndicatorCalculator.add_indicators(m5, "5m")
            }
            valid_symbols.append(symbol)
    
    if not valid_symbols:
        print("❌ No data fetched. Check internet or symbols.")
        return
    
    # Timeline based on earliest m5 index
    timeline = all_data[valid_symbols[0]]['m5'].index
    total_wins = 0
    total_losses = 0
    total_breakevens = 0
    trades = []
    
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    print(f"Simulating {len(timeline)} bars (M5 resolution)...")
    
    for t in timeline:
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            
            m5_df_full = all_data[symbol]['m5']
            if t not in m5_df_full.index: continue
            
            m5_idx = m5_df_full.index.get_loc(t)
            if m5_idx < 100: continue # Need history
            
            # State at time T
            state_m5 = m5_df_full.iloc[:m5_idx+1]
            latest_m5 = state_m5.iloc[-1]
            
            m15_df_full = all_data[symbol]['m15']
            state_m15 = m15_df_full[m15_df_full.index <= t]
            if state_m15.empty: continue
            latest_m15 = state_m15.iloc[-1]
            
            h1_df_full = all_data[symbol]['h1']
            state_h1 = h1_df_full[h1_df_full.index <= t]
            if state_h1.empty: continue
            latest_h1 = state_h1.iloc[-1]
            
            h4_df_full = all_data[symbol]['h4']
            state_h4 = h4_df_full[h4_df_full.index <= t]
            if state_h4.empty: continue
            
            # 1. Trend (H1)
            trend_ema = latest_h1[f'ema_{EMA_TREND}']
            if pd.isna(trend_ema): continue
            
            # 1. Sweep Detection (M15 with M5 fallback for Gold)
            now_hour = t.hour
            lookback = 50 if 13 <= now_hour <= 21 else 35 if 7 <= now_hour < 13 else 21
            
            # Gold Specialist: Aggressive Lookback for 1-signal/day target
            if symbol == "GC=F":
                lookback = 20
            
            def detect_sweep(df, lb):
                if len(df) <= lb: return None, None
                p_low = df.iloc[-(lb+1):-1]['low'].min()
                p_high = df.iloc[-(lb+1):-1]['high'].max()
                lat = df.iloc[-1]
                if lat['low'] < p_low < lat['close']: return "BUY", p_low
                if lat['high'] > p_high > lat['close']: return "SELL", p_high
                return None, None

            direction, sweep_level = detect_sweep(state_m15, lookback)
            
            # Gold Specialist: If no M15 sweep, check M5 for lower-tier institutional activity
            if not direction and symbol == "GC=F":
                m5_lb = lookback * 3 
                direction, sweep_level = detect_sweep(state_m5, m5_lb)
                
            if not direction: continue

            # 2. Trend Validation (H1)
            trend_ema = latest_h1[f'ema_{EMA_TREND}']
            if pd.isna(trend_ema): continue
            
            h1_trend = "BULLISH" if latest_h1['close'] > trend_ema else "BEARISH"
            
            # Gold Specialist: Lenient Trend (Within 1 ATR of EMA is acceptable)
            if symbol == "GC=F":
                h1_atr = latest_h1['atr']
                if abs(latest_h1['close'] - trend_ema) < h1_atr:
                    # Near-Trend Gold setups are forced to "Aligned"
                    pass 
                elif (direction == "BUY" and h1_trend != "BULLISH") or (direction == "SELL" and h1_trend != "BEARISH"):
                    continue
            else:
                if (direction == "BUY" and h1_trend != "BULLISH") or (direction == "SELL" and h1_trend != "BEARISH"):
                    continue
            
            # 3. V8.0 INTEGRATION: 4H Level Alignment & CRT
            h4_levels = IndicatorCalculator.get_h4_levels(state_h4)
            h4_sweep = False
            if h4_levels:
                if direction == "BUY" and latest_m15['low'] < h4_levels['prev_h4_low'] and latest_m15['close'] > h4_levels['prev_h4_low']:
                    h4_sweep = True
                elif direction == "SELL" and latest_m15['high'] > h4_levels['prev_h4_high'] and latest_m15['close'] < h4_levels['prev_h4_high']:
                    h4_sweep = True
            
            crt_validation = CRTAnalyzer.validate_setup(state_m15, direction)
            
            # 4. Filters & Confluences
            fvgs_m5 = ImbalanceDetector.detect_fvg(state_m5)
            has_fvg = ImbalanceDetector.is_price_in_fvg(latest_m5['close'], fvgs_m5, direction)
            if not has_fvg:
                fvgs_m15 = ImbalanceDetector.detect_fvg(state_m15)
                has_fvg = ImbalanceDetector.is_price_in_fvg(latest_m15['close'], fvgs_m15, direction)

            is_gold = (symbol == "GC=F")
            # Gold Specialist: Expanded Session (08:00 - 21:00 UTC)
            if is_gold:
                if not (time(8, 0) <= t.time() <= time(21, 0)):
                    continue
            else:
                if not SessionFilter.is_valid_session(t):
                    continue
            
            # Displacement confirmed on M15 for backtest consistency
            displaced = DisplacementAnalyzer.is_displaced(state_m15, direction)
            
            # 5. Scoring
            score_details = {
                'h1_aligned': True,
                'sweep_type': "M15_SWEEP",
                'displaced': displaced,
                'pullback': True, # Assume pullback/recovery on same bar or next
                'volatile': latest_m5['atr'] > latest_m5.get('atr_avg', 0),
                'h4_sweep': h4_sweep,
                'crt_bonus': crt_validation.get('score_bonus', 0),
                'symbol': symbol,
                'direction': direction,
                'has_fvg': has_fvg
            }
            # Add missing fields to avoid ScoringEngine issues
            score_details.update({
                'asian_sweep': False, 'asian_quality': False, # Asian range check is complex in backtest timeline
                'adr_exhausted': False, 'at_value': False, 'ema_slope': 0, 'h1_dist': 0
            })
            
            confidence = ScoringEngine.calculate_score(score_details)
            threshold = GOLD_CONFIDENCE_THRESHOLD if symbol == "GC=F" else MIN_CONFIDENCE_SCORE
            if confidence < threshold: continue
            
            # 6. Execute Trade
            from audit.optimizer import AutoOptimizer
            opt_mult = AutoOptimizer.get_multiplier_for_symbol(symbol)
            levels = EntryLogic.calculate_levels(state_m5, direction, sweep_level, latest_m5['atr'], symbol=symbol, opt_mult=opt_mult)
            
            m5_start_idx = m5_df_full.index.get_indexer([t], method='nearest')[0]
            hit = None
            tp0_hit = False
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df_full))):
                fut = m5_df_full.iloc[j]
                if direction == "BUY":
                    if fut['high'] >= levels['tp0']: tp0_hit = True
                    if tp0_hit and fut['low'] <= levels['entry']: hit = "BE"; break
                    if fut['low'] <= levels['sl']: hit = "LOSS"; break
                    if fut['high'] >= levels['tp2']: hit = "WIN"; break
                else:
                    if fut['low'] <= levels['tp0']: tp0_hit = True
                    if tp0_hit and fut['high'] >= levels['entry']: hit = "BE"; break
                    if fut['high'] >= levels['sl']: hit = "LOSS"; break
                    if fut['low'] <= levels['tp2']: hit = "WIN"; break
            
            if hit:
                r_val = 2.0 if hit == "WIN" else -1.0 if hit == "LOSS" else 0.5 if tp0_hit else 0.0
                trades.append({
                    't': t, 
                    'symbol': symbol, 
                    'dir': direction, 
                    'res': hit, 
                    'score': confidence, 
                    'r': r_val, 
                    'h4': h4_sweep, 
                    'crt': crt_validation['phase'],
                    'has_fvg': has_fvg,
                    'displaced': displaced,
                    'atr': latest_m5['atr'],
                    'confidence': confidence
                })
                if hit == "WIN": total_wins += 1
                elif hit == "LOSS": total_losses += 1
                elif hit == "BE": total_breakevens += 1
                cooldowns[symbol] = t + timedelta(hours=8)

    # Final Report
    print("\n" + "═"*55)
    print(f"🏁 V8.0 INSTITUTIONAL BACKTEST RESULTS")
    print(f"Period: {days} days")
    print(f"Total Trades: {len(trades)}")
    print(f"Wins: {total_wins} ✅ | Losses: {total_losses} ❌ | BE: {total_breakevens} 🛡️")
    
    total_r = sum(tr['r'] for tr in trades)
    wr = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
    print(f"Total R-Multiple: {total_r:+.1f}R")
    print(f"Adjusted Win Rate: {wr:.1f} %")
    print("═"*55)
    
    # Save to CSV for Audit
    if trades:
        df_audit = pd.DataFrame(trades)
        df_audit.to_csv("research/audit_results_v8.csv", index=False)
        print(f"📊 Audit logs exported to research/audit_results_v8.csv")

    # Analyze confluences
    h4_trades = [tr for tr in trades if tr['h4']]
    crt_trades = [tr for tr in trades if "DISTRIBUTION" in tr['crt']]
    
    if h4_trades:
        h4_wins = len([tr for tr in h4_trades if tr['res'] == "WIN"])
        h4_wr = (h4_wins / len(h4_trades) * 100)
        print(f"📈 4H Sweep Confluence: {len(h4_trades)} trades | WR: {h4_wr:.1f}%")
        
    if crt_trades:
        crt_wins = len([tr for tr in crt_trades if tr['res'] == "WIN"])
        crt_wr = (crt_wins / len(crt_trades) * 100)
        print(f"🚀 CRT Distribution Confluence: {len(crt_trades)} trades | WR: {crt_wr:.1f}%")

if __name__ == "__main__":
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(run_v8_backtest(d))
