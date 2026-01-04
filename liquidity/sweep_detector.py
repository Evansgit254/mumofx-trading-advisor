import pandas as pd
from config.config import LIQUIDITY_LOOKBACK, SWEEP_WICK_PERCENT

class LiquidityDetector:
    @staticmethod
    def detect_sweep(m1_df: pd.DataFrame, bias: str) -> dict:
        """
        Detects liquidity sweeps on M1.
        Returns sweep info if detected, else None.
        """
        if m1_df.empty or len(m1_df) < 2:
            return None

        latest_candle = m1_df.iloc[-1]
        prev_candles = m1_df.iloc[-(LIQUIDITY_LOOKBACK+1):-1]

        lookback_high = prev_candles['high'].max()
        lookback_low = prev_candles['low'].min()

        candle_range = latest_candle['high'] - latest_candle['low']
        if candle_range == 0:
            return None

        # Sweep of Highs (Potential SELL after sweep)
        if bias == "BEARISH":
            if latest_candle['high'] > lookback_high and latest_candle['close'] < lookback_high:
                upper_wick = latest_candle['high'] - max(latest_candle['open'], latest_candle['close'])
                if upper_wick / candle_range >= SWEEP_WICK_PERCENT:
                    return {
                        'type': 'BEARISH_SWEEP',
                        'level': lookback_high,
                        'description': f'Sweep of Recent High ({lookback_high:.5f})'
                    }

        # Sweep of Lows (Potential BUY after sweep)
        if bias == "BULLISH":
            if latest_candle['low'] < lookback_low and latest_candle['close'] > lookback_low:
                lower_wick = min(latest_candle['open'], latest_candle['close']) - latest_candle['low']
                if lower_wick / candle_range >= SWEEP_WICK_PERCENT:
                    return {
                        'type': 'BULLISH_SWEEP',
                        'level': lookback_low,
                        'description': f'Sweep of Recent Low ({lookback_low:.5f})'
                    }

        return None
