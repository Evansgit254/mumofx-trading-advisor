import asyncio
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ASIAN_RANGE_MIN_PIPS, ADR_THRESHOLD_PERCENT
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.correlation import CorrelationAnalyzer

async def run_audit(days=45):
    print(f"📊 STRATEGY FORENSIC AUDIT (Last {days} days)")
    print(f"Symbols: {SYMBOLS}")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("📥 Fetching historical data...")
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
    
    if not valid_symbols:
        print("❌ No data found for specified symbols.")
        return

    # Metrics collections
    trades = []
    daily_counts = {}
    
    # Session Definition (UTC)
    # Asian: 00-08, London: 08-13, NY: 13-21, Gap: 21-24
    
    timeline = all_data[valid_symbols[0]]['m15'].index
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    print(f"🔎 Simulating strategy on {len(timeline)} data points...")
    
    for t in timeline:
        potential_batch = []
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            
            m15_df = all_data[symbol]['m15']
            if t not in m15_df.index: continue
            
            idx = m15_df.index.get_loc(t)
            if idx < 100: continue
            
            state_m15 = m15_df.iloc[:idx+1]
            state_h1 = all_data[symbol]['h1'][all_data[symbol]['h1'].index <= t]
            m5_df = all_data[symbol]['m5']
            latest_m5 = m5_df[m5_df.index <= t].iloc[-1]
            
            if state_h1.empty: continue
            
            # Logic calculations
            h1_close = state_h1.iloc[-1]['close']
            h1_ema = state_h1.iloc[-1][f'ema_{EMA_TREND}']
            h1_trend_val = 1 if h1_close > h1_ema else -1
            
            # Liquidity Sweep (M15)
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend_val == 1 and state_m15.iloc[-1]['low'] < prev_low < state_m15.iloc[-1]['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend_val == -1 and state_m15.iloc[-1]['high'] > prev_high > state_m15.iloc[-1]['close']:
                direction = "SELL"; sweep_level = prev_high
            
            if not direction: continue
            
            # Displacement check
            displaced = DisplacementAnalyzer.is_displaced(state_m15, direction)
            
            # Scoring
            ema_slope = IndicatorCalculator.calculate_ema_slope(state_h1, f'ema_{EMA_TREND}')
            h1_dist = (h1_close - h1_ema) / h1_ema if h1_ema != 0 else 0
            
            score_details = {
                'h1_aligned': True, 'sweep_type': 'M15_SWEEP', 'displaced': displaced,
                'pullback': True, 'volatile': True, 'asian_sweep': False, 'asian_quality': True,
                'adr_exhausted': False, 'at_value': False, 'ema_slope': ema_slope, 
                'h1_dist': h1_dist, 'symbol': symbol, 'direction': direction
            }
            confidence = ScoringEngine.calculate_score(score_details)
            
            if confidence >= MIN_CONFIDENCE_SCORE:
                potential_batch.append({
                    'symbol': symbol, 
                    'pair': symbol.replace('=X', '').replace('^', ''),
                    'direction': direction, 't': t, 
                    'sweep_level': sweep_level, 'atr': latest_m5['atr']
                })

        if not potential_batch: continue
        filtered = CorrelationAnalyzer.filter_signals(potential_batch)
        
        for sig in filtered:
            symbol = sig['symbol']
            m5_df = all_data[symbol]['m5']
            levels = EntryLogic.calculate_levels(m5_df[m5_df.index <= sig['t']], sig['direction'], sig['sweep_level'], sig['atr'])
            m5_start_idx = m5_df.index.get_indexer([sig['t']], method='nearest')[0]
            
            result = "MISS" 
            tp0_hit = False
            tp1_hit = False
            
            # Simulate trade outcome (V7.0 Liquid Reaper)
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                fut = m5_df.iloc[j]
                if sig['direction'] == "BUY":
                    # TP0 - PARTIAL + MOVE TO BE
                    if fut['high'] >= levels['tp0']: tp0_hit = True
                    
                    # BE Execution
                    if tp0_hit and fut['low'] <= levels['entry']: 
                        result = "HALF_WIN" # We closed 50% at TP0, rest hit BE
                        break
                    
                    # SL Execution (Full Loss if TP0 not hit)
                    if not tp0_hit and fut['low'] <= levels['sl']: 
                        result = "LOSS"; break
                    
                    # TP1 (Lock in TP0 as new SL)
                    if fut['high'] >= levels['tp1']: tp1_hit = True
                    if tp1_hit and fut['low'] <= levels['tp0']:
                        result = "WIN_PARTIAL"; break # Hit TP1, trailed stop hit TP0
                    
                    # TP2 (Full Win)
                    if fut['high'] >= levels['tp2']: result = "WIN"; break
                else:
                    # SELL logic
                    if fut['low'] <= levels['tp0']: tp0_hit = True
                    if tp0_hit and fut['high'] >= levels['entry']: result = "HALF_WIN"; break
                    if not tp0_hit and fut['high'] >= levels['sl']: result = "LOSS"; break
                    
                    if fut['low'] <= levels['tp1']: tp1_hit = True
                    if tp1_hit and fut['high'] >= levels['tp0']: result = "WIN_PARTIAL"; break
                    
                    if fut['low'] <= levels['tp2']: result = "WIN"; break
            
            if result != "MISS":
                hour = sig['t'].hour
                session = "Asian" if 0 <= hour < 8 else "London" if 8 <= hour < 13 else "NY" if 13 <= hour < 21 else "Transition"
                
                trade_record = {
                    'symbol': symbol, 'direction': sig['direction'], 'time': sig['t'],
                    'result': result, 'session': session, 'date': sig['t'].date()
                }
                trades.append(trade_record)
                
                # Cooldown
                cooldowns[symbol] = sig['t'] + timedelta(hours=6)

    # --- REPORTING ---
    df_trades = pd.DataFrame(trades)
    
    if df_trades.empty:
        print("No trades found in backtest period.")
        return

    total_days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days
    unique_trade_days = df_trades['date'].nunique()
    
    daily_trades = df_trades.groupby('date').size()
    avg_trades_daily = daily_trades.mean()
    
    print("\n" + "═"*50)
    print(f"🎯 AUDIT RESULTS: {days} Day Period")
    print(f"Total Trades Taken: {len(df_trades)}")
    print(f"Trade Day Probability: {(unique_trade_days/total_days*100):.1f}% (Chance of getting a setup today)")
    print(f"Avg Trades per Day: {avg_trades_daily:.1f}")
    print(f"Symbol with most trades: {df_trades['symbol'].value_counts().idxmax()} ({df_trades['symbol'].value_counts().max()})")
    
    gold_trades = df_trades[df_trades['symbol'] == 'GC=F']
    if not gold_trades.empty:
        gold_v7_wins = len(gold_trades[gold_trades['result'].isin(['WIN', 'WIN_PARTIAL', 'HALF_WIN'])])
        gold_losses = len(gold_trades[gold_trades['result'] == 'LOSS'])
        gold_total = gold_v7_wins + gold_losses
        gold_wr = (gold_v7_wins / gold_total * 100) if gold_total > 0 else 0
        print(f"🏆 GOLD (XAUUSD) PERFORMANCE: {len(gold_trades)} trades | V7 Success Rate: {gold_wr:.1f}%")
    
    print("\n⏳ PERFORMANCE BY SESSION:")
    session_stats = df_trades.groupby('session').size()
    for sess, count in session_stats.items():
        sess_v7_wins = len(df_trades[(df_trades['session'] == sess) & (df_trades['result'].isin(['WIN', 'WIN_PARTIAL', 'HALF_WIN']))])
        sess_losses = len(df_trades[(df_trades['session'] == sess) & (df_trades['result'] == 'LOSS')])
        sess_total = sess_v7_wins + sess_losses
        wr = (sess_v7_wins / sess_total * 100) if sess_total > 0 else 0
        print(f"• {sess}: {count} trades | V7 Win Rate: {wr:.1f}%")
        
    print("\n📅 PERFORMANCE BY DAY OF WEEK:")
    df_trades['dow'] = pd.to_datetime(df_trades['date']).dt.day_name()
    dow_stats = df_trades.groupby('dow').size().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    for dow, count in dow_stats.items():
        print(f"• {dow}: {count} trades")

    print("\n✅ OVERALL WIN RATE (Excl. BE):")
    total_w = len(df_trades[df_trades['result'] == 'WIN'])
    total_l = len(df_trades[df_trades['result'] == 'LOSS'])
    total_be = len(df_trades[df_trades['result'] == 'BE'])
    
    print(f"Wins: {total_w} | Losses: {total_l} | Breakevens: {total_be}")
    
    # V7.0 Audit logic
    v7_wins = len(df_trades[df_trades['result'].isin(['WIN', 'WIN_PARTIAL', 'HALF_WIN'])])
    print(f"V7.0 Successes (Profit Taken): {v7_wins}")
    print(f"Win Rate: {(v7_wins/(v7_wins+total_l)*100):.1f}%")
    print("═"*50)

if __name__ == "__main__":
    asyncio.run(run_audit(45))
