import pandas as pd
from config.config import DISPLACEMENT_BODY_PERCENT

class DisplacementAnalyzer:
    @staticmethod
    def is_displaced(m1_df: pd.DataFrame, direction: str) -> bool:
        """
        Confirms smart money intent via displacement candle.
        direction: 'BUY' or 'SELL'
        """
        if m1_df.empty or len(m1_df) < 1:
            return False

        latest = m1_df.iloc[-1]
        body = abs(latest['close'] - latest['open'])
        candle_range = latest['high'] - latest['low']

        if candle_range == 0:
            return False

        body_ratio = body / candle_range
        
        is_strong = body_ratio >= DISPLACEMENT_BODY_PERCENT
        
        if direction == "BUY":
            return is_strong and latest['close'] > latest['open']
        elif direction == "SELL":
            return is_strong and latest['close'] < latest['open']
        
        return False
