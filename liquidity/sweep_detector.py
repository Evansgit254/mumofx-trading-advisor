import pandas as pd
from config.config import LIQUIDITY_LOOKBACK, SWEEP_WICK_PERCENT

class LiquidityDetector:
    @staticmethod
    def detect_sweep(df: pd.DataFrame, bias: str, timeframe: str = "m15") -> dict:
        """
        Detects liquidity sweeps on a given timeframe.
        """
        if df.empty or len(df) < 50:
            return None

        latest_candle = df.iloc[-1]
        prev_candles = df.iloc[-(LIQUIDITY_LOOKBACK+1):-1]

        lookback_high = prev_candles['high'].max()
        lookback_low = prev_candles['low'].min()

        candle_range = latest_candle['high'] - latest_candle['low']
        if candle_range == 0:
            return None

        # Sweep of Highs (Potential SELL)
        if bias == "BEARISH":
            if latest_candle['high'] > lookback_high and latest_candle['close'] < lookback_high:
                upper_wick = latest_candle['high'] - max(latest_candle['open'], latest_candle['close'])
                if upper_wick / candle_range >= SWEEP_WICK_PERCENT:
                    return {
                        'type': f'{timeframe.upper()}_BEARISH_SWEEP',
                        'level': lookback_high,
                        'description': f'Sweep of {timeframe.upper()} High ({lookback_high:.5f})'
                    }

        # Sweep of Lows (Potential BUY)
        if bias == "BULLISH":
            if latest_candle['low'] < lookback_low and latest_candle['close'] > lookback_low:
                lower_wick = min(latest_candle['open'], latest_candle['close']) - latest_candle['low']
                if lower_wick / candle_range >= SWEEP_WICK_PERCENT:
                    return {
                        'type': f'{timeframe.upper()}_BULLISH_SWEEP',
                        'level': lookback_low,
                        'description': f'Sweep of {timeframe.upper()} Low ({lookback_low:.5f})'
                    }

        return None
