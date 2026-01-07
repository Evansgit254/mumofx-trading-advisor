from config.config import ACCOUNT_BALANCE, RISK_PER_TRADE_PERCENT, MIN_LOT_SIZE
import pandas as pd
import sqlite3
import os

class RiskManager:
    # Approximate pip values for 0.01 lot (1,000 units)
    # Most majors are $0.10 per pip for 0.01 lot
    PIP_VALUE_001 = {
        "EURUSD": 0.10,
        "GBPUSD": 0.10,
        "AUDUSD": 0.10,
        "USDCAD": 0.075, # Approx
        "NZDUSD": 0.10,
        "USDJPY": 0.065, # Approx at ~150 rate
        "GC": 0.10,      # Gold is ~$1 per $0.1 move for 1 lot, so 0.10 for 0.01 depending on contract
        "GSPC": 0.05,    # S&P 500 mini/micro varies, using conservative estimate
        "IXIC": 0.05     # Nasdaq
    }

    @staticmethod
    def calculate_lot_size(symbol: str, entry: float, sl: float, db_path="database/signals.db") -> dict:
        """
        Calculates the recommended lot size with V7.0 Dynamic Scaling.
        Adjusts risk based on recent performance streaks.
        """
        import sqlite3
        import os
        
        base_risk_pct = RISK_PER_TRADE_PERCENT
        multiplier = 1.0
        
        # V7.0 Performance-Based Scaling
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                # Get last 5 resolved trades
                query = "SELECT status FROM signals WHERE status IN ('WIN', 'LOSS', 'BREAKEVEN') ORDER BY timestamp DESC LIMIT 5"
                recent_trades = pd.read_sql_query(query, conn)['status'].tolist()
                conn.close()
                
                if recent_trades:
                    # Streak Logic
                    win_streak = 0
                    loss_streak = 0
                    for status in recent_trades:
                        if status == 'WIN': win_streak += 1
                        elif status == 'LOSS': loss_streak += 1
                        else: break # Break on breakeven
                    
                    if win_streak >= 3: multiplier = 1.25 # Reward 3+ wins
                    elif loss_streak >= 2: multiplier = 0.75 # Protect after 2 losses
            except:
                pass

        risk_amount = ACCOUNT_BALANCE * (base_risk_pct / 100) * multiplier
        
        # Calculate SL distance in "pips"
        sl_distance = abs(entry - sl)
        
        # Normalization for different asset types
        if "JPY" in symbol:
            pips = sl_distance * 100
        elif "GC" in symbol or "GSPC" in symbol or "IXIC" in symbol:
            pips = sl_distance 
        else:
            pips = sl_distance * 10000

        # Find pip value for this symbol
        key = symbol.replace("=X", "").replace("^", "")
        pip_val = RiskManager.PIP_VALUE_001.get(key, 0.10)
        
        if pips == 0: return {"lots": MIN_LOT_SIZE, "risk_cash": 0}

        # Calculation: (Risk Amount / (Pip Value 0.01 * Pips)) * 0.01
        recommended_lots = (risk_amount / (pip_val * pips)) * 0.01
        
        # Round to 2 decimal places and ensure minimum
        final_lots = max(MIN_LOT_SIZE, round(recommended_lots, 2))
        
        # Check if this risk exceeds 10% of account (absolute safety)
        actual_risk = (final_lots / 0.01) * pip_val * pips
        risk_warning = ""
        if actual_risk > (ACCOUNT_BALANCE * 0.10):
            risk_warning = "⚠️ *HIGH RISK:* This SL is very wide for a $50 account."

        return {
            'lots': final_lots,
            'risk_cash': round(actual_risk, 2),
            'risk_percent': round((actual_risk / ACCOUNT_BALANCE) * 100, 1),
            'pips': round(pips, 1),
            'warning': risk_warning
        }

    @staticmethod
    def calculate_layers(total_lots: float, entry: float, sl: float, direction: str, quality: str = "B") -> list:
        """
        Splits total lot size into strategic layers based on setup quality.
        """
        if quality == "A+":
            # A+ setups use aggressive "Load the Boat" layering
            # 50% Market, 30% Retest, 20% Extreme Retest
            l1_lots = max(MIN_LOT_SIZE, round(total_lots * 0.5, 2))
            l2_lots = max(MIN_LOT_SIZE, round(total_lots * 0.3, 2))
            l3_lots = max(MIN_LOT_SIZE, round(total_lots * 0.2, 2))
        else:
            # Standard setups use balanced layering
            # 40% (Market), 40% (Retest), 20% (Defensive)
            l1_lots = max(MIN_LOT_SIZE, round(total_lots * 0.4, 2))
            l2_lots = max(MIN_LOT_SIZE, round(total_lots * 0.4, 2))
            l3_lots = max(MIN_LOT_SIZE, round(total_lots * 0.2, 2))
        
        # Calculate Price Levels for Layers
        dist = abs(entry - sl)
        if direction == "BUY":
            l1_price = entry
            l2_price = entry - (dist * 0.3) # 30% pullback
            l3_price = entry - (dist * 0.6) # 60% deep retest
        else:
            l1_price = entry
            l2_price = entry + (dist * 0.3)
            l3_price = entry + (dist * 0.6)
            
        return [
            {'label': f'Aggressive Layer ({"50%" if quality=="A+" else "40%"})', 'price': l1_price, 'lots': l1_lots},
            {'label': f'Optimal Retest ({"30%" if quality=="A+" else "40%"})', 'price': l2_price, 'lots': l2_lots},
            {'label': 'Safety Layer (20%)', 'price': l3_price, 'lots': l3_lots}
        ]
