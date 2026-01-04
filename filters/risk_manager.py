from config.config import ACCOUNT_BALANCE, RISK_PER_TRADE_PERCENT, MIN_LOT_SIZE

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
    def calculate_lot_size(symbol: str, entry: float, sl: float) -> dict:
        """
        Calculates the recommended lot size for a $50 account.
        """
        risk_amount = ACCOUNT_BALANCE * (RISK_PER_TRADE_PERCENT / 100)
        
        # Calculate SL distance in "pips" (simplified)
        # For FX, 0.0001 is 1 pip
        sl_distance = abs(entry - sl)
        
        # Normalization for different asset types
        if "JPY" in symbol:
            pips = sl_distance * 100
        elif "GC" in symbol or "GSPC" in symbol or "IXIC" in symbol:
            pips = sl_distance # Using points for indices/gold
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
