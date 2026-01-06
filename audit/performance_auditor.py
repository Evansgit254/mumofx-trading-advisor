import asyncio
import pandas as pd
from datetime import datetime
from audit.journal import SignalJournal
from data.fetcher import DataFetcher
from config.config import SYMBOLS

class PerformanceAuditor:
    def __init__(self):
        self.journal = SignalJournal()
        self.fetcher = DataFetcher()

    async def resolve_pending_trades(self):
        print("🔍 Auditing Live Performance...")
        pending = self.journal.get_pending_signals()
        
        if not pending:
            print("✅ No pending trades to audit.")
            return

        for signal in pending:
            symbol = signal['symbol']
            t_start = pd.to_datetime(signal['timestamp'])
            
            # Fetch data from signal time to now
            df = DataFetcher.fetch_range(symbol, "5m", start=t_start.strftime("%Y-%m-%d"), end=datetime.now().strftime("%Y-%m-%d"))
            
            if df is None or df.empty:
                continue
            
            # Filter to only look at bars AFTER the signal
            trade_action = df[df.index >= t_start]
            
            if len(trade_action) < 12: # Wait at least 1 hour (12 * 5m) before final resolution
                continue
                
            entry = signal['entry_price']
            sl = signal['sl']
            tp0 = signal['tp0']
            tp1 = signal['tp1']
            tp2 = signal['tp2']
            direction = signal['direction']
            
            result_status = 'PENDING'
            result_pips = 0
            
            hit_tp0 = False
            hit_tp1 = False
            
            for _, bar in trade_action.iterrows():
                if direction == 'BUY':
                    if not hit_tp0 and bar['high'] >= tp0: hit_tp0 = True
                    if hit_tp0 and not hit_tp1 and bar['high'] >= tp1: hit_tp1 = True
                    
                    if bar['high'] >= tp2:
                        result_status = 'WIN'
                        result_pips = abs(tp2 - entry) * 10000
                        break
                    
                    # Trailing Logic
                    curr_sl = sl
                    if hit_tp1: curr_sl = tp0
                    elif hit_tp0: curr_sl = entry
                    
                    if bar['low'] <= curr_sl:
                        result_status = 'BE' if curr_sl == entry else 'WIN_PARTIAL' if curr_sl == tp0 else 'LOSS'
                        result_pips = (curr_sl - entry) * 10000
                        break
                else: # SELL
                    if not hit_tp0 and bar['low'] <= tp0: hit_tp0 = True
                    if hit_tp0 and not hit_tp1 and bar['low'] <= tp1: hit_tp1 = True
                    
                    if bar['low'] <= tp2:
                        result_status = 'WIN'
                        result_pips = abs(tp2 - entry) * 10000
                        break
                        
                    curr_sl = sl
                    if hit_tp1: curr_sl = tp0
                    elif hit_tp0: curr_sl = entry
                    
                    if bar['high'] >= curr_sl:
                        result_status = 'BE' if curr_sl == entry else 'WIN_PARTIAL' if curr_sl == tp0 else 'LOSS'
                        result_pips = (entry - curr_sl) * 10000
                        break
            
            if result_status != 'PENDING':
                print(f"✅ Resolved {symbol} @ {t_start}: {result_status} ({result_pips:.1f} pips)")
                self.journal.update_signal_result(signal['id'], result_status, result_pips)

if __name__ == "__main__":
    auditor = PerformanceAuditor()
    asyncio.run(auditor.resolve_pending_trades())
