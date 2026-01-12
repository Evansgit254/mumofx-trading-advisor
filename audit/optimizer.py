import sqlite3
import pandas as pd
import os
from config.config import ATR_MULTIPLIER

class AutoOptimizer:
    def __init__(self, db_path="database/signals.db"):
        self.db_path = db_path

    def get_optimized_multipliers(self, verbose=False):
        """
        Analyzes past trades to suggest better TP multipliers.
        Goal: If a symbol hits BE too often, suggest tightening/widening targets.
        """
        try:
            df = pd.DataFrame()
            if os.path.exists(self.db_path):
                with sqlite3.connect(self.db_path) as conn:
                    # Get last 50 trades
                    query = "SELECT symbol, status FROM signals WHERE status IN ('WIN', 'LOSS', 'BE', 'WIN_PARTIAL', 'PARTIAL_LOSS') ORDER BY id DESC LIMIT 50"
                    df = pd.read_sql_query(query, conn)
            
            # Fallback to backtest CSV for iterative research
            if df.empty and os.path.exists("research/audit_results_v8.csv"):
                df = pd.read_csv("research/audit_results_v8.csv")
                if 'res' in df.columns: df = df.rename(columns={'res': 'status'})
                
            if df.empty:
                return {}

            multipliers = {}
            for symbol in df['symbol'].unique():
                symbol_trades = df[df['symbol'] == symbol]
                total = len(symbol_trades)
                be_count = len(symbol_trades[symbol_trades['status'].isin(['BE', 'PARTIAL_LOSS'])])
                loss_count = len(symbol_trades[symbol_trades['status'] == 'LOSS'])
                
                be_rate = be_count / total if total > 0 else 0
                
                # Logic: 
                # If high BE rate (>40%), it means TP2 is too far or price stalls AFTER TP0.
                # Narrowing the TP2 might convert some BEs into WINS.
                # If low BE rate but high loss rate, price is hunting wicks. 
                
                mult = ATR_MULTIPLIER # Default 1.5
                
                if be_rate > 0.4:
                    mult = 1.2 # Tighten for quicker exits
                    if verbose: print(f"📉 [OPTIMIZER] Tightening {symbol} TP to {mult}x (High BE Rate: {be_rate*100:.1f}%)")
                elif be_rate < 0.1 and total >= 5:
                    mult = 1.8 # Reward stable runners
                    if verbose: print(f"🚀 [OPTIMIZER] Expanding {symbol} TP to {mult}x (Low BE Rate: {be_rate*100:.1f}%)")
                    
                multipliers[symbol] = mult
                
            return multipliers
        except Exception as e:
            print(f"❌ [OPTIMIZER] Error: {e}")
            return {}

    @classmethod
    def get_multiplier_for_symbol(cls, symbol, db_path="database/signals.db"):
        opt = cls(db_path)
        mults = opt.get_optimized_multipliers()
        return mults.get(symbol, ATR_MULTIPLIER)
