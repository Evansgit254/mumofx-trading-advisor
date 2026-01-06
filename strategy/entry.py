import pandas as pd
from config.config import RSI_BUY_LOW, RSI_BUY_HIGH, RSI_SELL_LOW, RSI_SELL_HIGH, EMA_FAST, ATR_MULTIPLIER

class EntryLogic:
    @staticmethod
    def check_pullback(df: pd.DataFrame, direction: str) -> dict:
        """
        Checks for pullback to EMA20 and RSI confirmation.
        Returns entry details if valid.
        """
        if df.empty or len(df) < 2:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        ema20 = latest[f'ema_{EMA_FAST}']
        rsi = latest['rsi']
        prev_rsi = prev['rsi']

        # Entry Zone: Price within a small buffer of EMA20
        # For simplicity, we check if price is pulling back towards EMA20 
        # and RSI is hitting the threshold.

        if direction == "BUY":
            # RSI pulls back to 25-40, then closes back above 40
            if prev_rsi <= RSI_BUY_HIGH and rsi > RSI_BUY_HIGH:
                # Confirm price is near EMA20 (or was recently)
                if latest['low'] <= ema20 * 1.001: # Allowing 0.1% buffer
                    return {
                        'entry_price': latest['close'],
                        'ema_zone': ema20,
                        'rsi_val': rsi
                    }

        if direction == "SELL":
            # RSI pulls back to 60-75, then closes back below 60
            if prev_rsi >= RSI_SELL_LOW and rsi < RSI_SELL_LOW:
                if latest['high'] >= ema20 * 0.999: # Allowing 0.1% buffer
                    return {
                        'entry_price': latest['close'],
                        'ema_zone': ema20,
                        'rsi_val': rsi
                    }

        return None

    @staticmethod
    def calculate_levels(df: pd.DataFrame, direction: str, sweep_level: float, atr: float, t=None):
        """
        Calculates Stop Loss and Take Profit levels (V8.0 Session Adaptive).
        """
        latest_price = df.iloc[-1]['close']
        
        # Session Tuning (V8.0)
        # Default TP2 multiplier is 1.5
        tp2_mult = ATR_MULTIPLIER 
        
        if t:
            hour = t.hour
            # NY Session (13-21 UTC): High Volatility -> Target Higher Gains
            if 13 <= hour <= 21:
                tp2_mult = 2.0 
            # Asian Session (00-08 UTC): Range Bound -> Target Quicker Exits
            elif 0 <= hour <= 8:
                tp2_mult = 1.2
        
        if direction == "BUY":
            sl = sweep_level - (0.5 * atr)
            tp0 = latest_price + (0.5 * atr)
            tp1 = latest_price + (1.0 * atr)
            tp2 = latest_price + (tp2_mult * atr)
        else:
            sl = sweep_level + (0.5 * atr)
            tp0 = latest_price - (0.5 * atr)
            tp1 = latest_price - (1.0 * atr)
            tp2 = latest_price - (tp2_mult * atr)
            
        return {
            'entry': latest_price,
            'sl': sl,
            'tp0': tp0,
            'tp1': tp1,
            'tp2': tp2,
            'tp2_mult': tp2_mult
        }
