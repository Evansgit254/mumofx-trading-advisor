import pandas as pd
from config.config import EMA_FAST, EMA_SLOW, EMA_TREND

class BiasAnalyzer:
    @staticmethod
    def get_bias(h1_df: pd.DataFrame, m15_df: pd.DataFrame) -> str:
        """
        Determines the Top-Down bias.
        H1 Trends + M15 Structure alignment.
        """
        if h1_df.empty or m15_df.empty:
            return "NEUTRAL"
            
        h1_latest = h1_df.iloc[-1]
        m15_latest = m15_df.iloc[-1]
        
        # 1. H1 Narrative (EMA 200)
        h1_trend = "BULLISH" if h1_latest['close'] > h1_latest[f'ema_{EMA_TREND}'] else "BEARISH"
        
        # 2. M15 Structural Alignment (EMA 20/50)
        m15_ema20 = m15_latest[f'ema_{EMA_FAST}']
        m15_ema50 = m15_latest[f'ema_{EMA_SLOW}']
        
        m15_bias = "NEUTRAL"
        if m15_ema20 > m15_ema50 and m15_latest['close'] > m15_ema20:
            m15_bias = "BULLISH"
        elif m15_ema20 < m15_ema50 and m15_latest['close'] < m15_ema20:
            m15_bias = "BEARISH"
            
        # 3. Final Convergence
        if h1_trend == "BULLISH" and m15_bias == "BULLISH":
            return "BULLISH"
        if h1_trend == "BEARISH" and m15_bias == "BEARISH":
            return "BEARISH"
            
        return "NEUTRAL"

    @staticmethod
    def get_h1_trend(h1_df: pd.DataFrame) -> str:
        if h1_df.empty: return "NEUTRAL"
        latest = h1_df.iloc[-1]
        return "BULLISH" if latest['close'] > latest[f'ema_{EMA_TREND}'] else "BEARISH"
