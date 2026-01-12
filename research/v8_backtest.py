import asyncio
import pandas as pd
import joblib
import os
import sys
from datetime import datetime, timedelta, time
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, GOLD_CONFIDENCE_THRESHOLD, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS, DXY_SYMBOL, TNX_SYMBOL, INSTITUTIONAL_TF
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from strategy.imbalance import ImbalanceDetector
from strategy.crt import CRTAnalyzer
from filters.session_filter import SessionFilter
from strategies.smc_strategy import SMCStrategy
from strategies.breakout_strategy import BreakoutStrategy
from strategies.price_action_strategy import PriceActionStrategy
from audit.performance_analyzer import PerformanceAnalyzer
from audit.optimizer import AutoOptimizer

# Performance Tuning
os.environ['DISABLE_AI_GRADER'] = 'true'

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_v8_backtest(days=30):
    print(f"🚀 V8.0 INSTITUTIONAL BACKTEST (Last {days} days)")
    print(f"Symbols: {SYMBOLS}")
    print(f"Institutional TF: {INSTITUTIONAL_TF}")
    print(f"CRT Validation: ACTIVE")
    
    # Fetch extra 10 days to allow for 100-period indicators on HTFs
    start_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    test_start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("Fetching data...")
    # Fetch DXY first
    dxy_h1 = DataFetcher.fetch_range(DXY_SYMBOL, "1h", start=start_date, end=end_date)
    if dxy_h1 is not None and not dxy_h1.empty:
        dxy_h1 = IndicatorCalculator.add_indicators(dxy_h1, "h1")
        
    # Fetch TNX (Macro Confluence)
    tnx_h1 = DataFetcher.fetch_range(TNX_SYMBOL, "1h", start=start_date, end=end_date)
    if tnx_h1 is not None and not tnx_h1.empty:
        tnx_h1 = IndicatorCalculator.add_indicators(tnx_h1, "h1")
    
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
    
    # Timeline based on earliest m5 index, filtered to the requested test period
    full_timeline = all_data[valid_symbols[0]]['m5'].index
    timeline = full_timeline[full_timeline >= test_start_date]
    total_wins = 0
    total_losses = 0
    total_breakevens = 0
    trades = []
    
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    # Initialize Strategies
    strategies = [SMCStrategy(), BreakoutStrategy(), PriceActionStrategy()]
    analyzer = PerformanceAnalyzer()
    analyzer.calculate_weights()
    
    # Initialize performance caching
    cached_multipliers = AutoOptimizer().get_optimized_multipliers(verbose=False)
    
    print(f"Simulating {len(timeline)} bars (M5 resolution)...")
    
    for i, t in enumerate(timeline):
        if i % 1000 == 0:
            print(f"Progress: {i}/{len(timeline)} bars ({(i/len(timeline))*100:.1f}%)")
        
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            
            m5_df_full = all_data[symbol]['m5']
            if t not in m5_df_full.index: continue
            
            m5_idx = m5_df_full.index.get_loc(t)
            if m5_idx < 200: continue
            
            m15_df_full = all_data[symbol]['m15']
            m15_idx = m15_df_full.index.get_indexer([t], method='pad')[0]
            
            h1_df_full = all_data[symbol]['h1']
            h1_idx = h1_df_full.index.get_indexer([t], method='pad')[0]
            
            h4_df_full = all_data[symbol]['h4']
            h4_idx = h4_df_full.index.get_indexer([t], method='pad')[0]

            # Fast Views (iloc slicing returns views, not copies in many cases)
            state_m5 = m5_df_full.iloc[:m5_idx+1]
            state_m15 = m15_df_full.iloc[:m15_idx+1]
            state_h1 = h1_df_full.iloc[:h1_idx+1]
            state_h4 = h4_df_full.iloc[:h4_idx+1]
            
            latest_m5 = m5_df_full.iloc[m5_idx]
            latest_m15 = m15_df_full.iloc[m15_idx]
            latest_h1 = h1_df_full.iloc[h1_idx]

            # Simplified Market context for speed
            market_context = {'DXY': None, '^TNX': None}

            for strategy in strategies:
                try:
                    signal = await strategy.analyze(symbol, {
                        'h1': state_h1, 'h4': state_h4, 'm15': state_m15, 'm5': state_m5
                    }, [], market_context) 
                    
                    if not signal: continue
                    
                    # Apply Dynamic Strategy Multiplier
                    multiplier = PerformanceAnalyzer.get_strategy_multiplier(strategy.get_id())
                    if strategy.get_id() == "smc_institutional": multiplier = 1.0 
                    confidence = round(signal['confidence'] * multiplier, 1)
                    
                    threshold = GOLD_CONFIDENCE_THRESHOLD if symbol == "GC=F" else MIN_CONFIDENCE_SCORE
                    if confidence < threshold: continue
                    
                    # Execute Trade
                    opt_mult = cached_multipliers.get(symbol, ATR_MULTIPLIER)
                    levels = EntryLogic.calculate_levels(state_m5, signal['direction'], signal.get('sweep_level', latest_m5['close']), latest_m5['atr'], symbol=symbol, opt_mult=opt_mult)
                    
                    m5_start_idx = m5_df_full.index.get_indexer([t], method='nearest')[0]
                    hit = None
                    tp0_hit = False
                    be_active = False
                    direction = signal['direction']
                    entry_p = signal['entry_price']
                    
                    from config.config import PARTIAL_SIZE, BE_TRIGGER_ATR
                    
                    for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df_full))):
                        fut = m5_df_full.iloc[j]
                        if direction == "BUY":
                            if fut['high'] >= levels['tp0']: tp0_hit = True
                            if fut['high'] >= levels['be_trigger']: be_active = True
                            
                            if fut['low'] <= levels['sl']:
                                hit = "LOSS"
                                if tp0_hit: hit = "PARTIAL_LOSS" # Hit TP0 then SL before BE
                                break
                            if be_active and fut['low'] <= entry_p:
                                hit = "BE"
                                break
                            if fut['high'] >= levels['tp2']:
                                hit = "WIN"
                                break
                        else:
                            if fut['low'] <= levels['tp0']: tp0_hit = True
                            if fut['low'] <= levels['be_trigger']: be_active = True
                            
                            if fut['high'] >= levels['sl']:
                                hit = "LOSS"
                                if tp0_hit: hit = "PARTIAL_LOSS"
                                break
                            if be_active and fut['high'] >= entry_p:
                                hit = "BE"
                                break
                            if fut['low'] <= levels['tp2']:
                                hit = "WIN"
                                break
                    
                    if hit:
                        # R-Multiple Calculation with PARTIAL_SIZE (default 0.5)
                        # Assumes entry-to-sl is roughly 1R distance for simplicity in this V8 mock
                        # TP0 (0.5 ATR) is approx 1R if SL is 0.5 ATR from entry
                        r_tp0 = 1.0 # 1R gain on half
                        r_sl = -1.0 # 1R loss on half
                        r_tp2 = 3.0 # Approx 3R gain on half (if TP2 is 1.5 ATR)
                        
                        if hit == "WIN":
                            r_val = (PARTIAL_SIZE * r_tp0) + ((1-PARTIAL_SIZE) * r_tp2)
                        elif hit == "BE":
                            r_val = (PARTIAL_SIZE * r_tp0) + ((1-PARTIAL_SIZE) * 0)
                        elif hit == "PARTIAL_LOSS":
                            r_val = (PARTIAL_SIZE * r_tp0) + ((1-PARTIAL_SIZE) * r_sl)
                        else: # Full LOSS
                            r_val = -1.0
                            
                        trades.append({
                            't': t, 
                            'symbol': symbol, 
                            'dir': direction, 
                            'res': hit, 
                            'score': confidence, 
                            'r': r_val, 
                            'strategy_id': strategy.get_id(),
                            'confidence': confidence,
                            'tp0_hit': tp0_hit,
                            'be_active': be_active
                        })
                        if hit == "WIN": total_wins += 1
                        elif hit == "LOSS": total_losses += 1
                        elif hit == "BE": total_breakevens += 1
                        
                        cooldowns[symbol] = t + timedelta(hours=4) # Shorter cooldown for independent strategies
                        break # Only one strategy per bar per symbol for backtest consistency
                except Exception as e:
                    print(f"ERROR executing strategy {strategy.get_id()} for {symbol}: {e}")
                    continue
            
            # Strategy loop ends

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
    h4_trades = [tr for tr in trades if tr.get('h4')]
    crt_trades = [tr for tr in trades if "DISTRIBUTION" in tr.get('crt', '')]
    
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
