import pandas as pd
from config.config import EMA_FAST, EMA_SLOW

class BiasAnalyzer:
    @staticmethod
    def get_bias(m5_df: pd.DataFrame) -> str:
        """
        Determines the bias based on M5 EMAs and price action.
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        if m5_df.empty or len(m5_df) < 2:
            return "NEUTRAL"

        latest = m5_df.iloc[-1]
        ema20 = latest[f'ema_{EMA_FAST}']
        ema50 = latest[f'ema_{EMA_SLOW}']
        price = latest['close']

        # Bullish: EMA20 > EMA50 and Price > EMA20
        if ema20 > ema50 and price > ema20:
            return "BULLISH"
        
        # Bearish: EMA20 < EMA50 and Price < EMA20
        if ema20 < ema50 and price < ema20:
            return "BEARISH"

        return "NEUTRAL"

    @staticmethod
    def is_choppy(m5_df: pd.DataFrame) -> bool:
        """
        Detects choppy market structure.
        """
        if len(m5_df) < 10:
            return True
        
        # Simple chop detection: price crossing EMA50 frequently
        crosses = ((m5_df['close'] > m5_df[f'ema_{EMA_SLOW}']) & (m5_df['close'].shift(1) < m5_df[f'ema_{EMA_SLOW}'].shift(1))) | \
                  ((m5_df['close'] < m5_df[f'ema_{EMA_SLOW}']) & (m5_df['close'].shift(1) > m5_df[f'ema_{EMA_SLOW}'].shift(1)))
        
        if crosses.tail(10).sum() > 4:
            return True
        
        return False
