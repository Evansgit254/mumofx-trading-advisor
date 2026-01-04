import pandas as pd
import pandas_ta as ta
from config.config import EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD, ATR_AVG_PERIOD, EMA_TREND, ADR_PERIOD, ASIAN_SESSION_START, ASIAN_SESSION_END
from datetime import time

class IndicatorCalculator:
    @staticmethod
    def add_indicators(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Adds EMA, RSI, and ATR to the dataframe.
        """
        if df.empty:
            return df

        # EMAs
        df[f'ema_{EMA_FAST}'] = ta.ema(df['close'], length=EMA_FAST)
        df[f'ema_{EMA_SLOW}'] = ta.ema(df['close'], length=EMA_SLOW)
        
        if timeframe == "h1":
            df[f'ema_{EMA_TREND}'] = ta.ema(df['close'], length=EMA_TREND)

        # RSI
        df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)

        # ATR
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD)
        
        # ATR Average for volatility filter
        df['atr_avg'] = df['atr'].rolling(window=ATR_AVG_PERIOD).mean()

        return df

    @staticmethod
    def get_market_structure(df: pd.DataFrame) -> pd.DataFrame:
        """
        Basic HH/LL identification.
        """
        # Simplistic HH/LL for now, can be refined
        df['hh'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
        df['ll'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
        return df

    @staticmethod
    def calculate_adr(h1_df: pd.DataFrame) -> float:
        """
        Calculates the Average Daily Range (High - Low) from H1 data.
        """
        if h1_df.empty: return 0.0
        # Group by day and calculate (High - Low)
        daily_ranges = h1_df.groupby(h1_df.index.date).apply(lambda x: x['high'].max() - x['low'].min())
        return daily_ranges.tail(ADR_PERIOD).mean()

    @staticmethod
    def get_asian_range(df: pd.DataFrame) -> dict:
        """
        Extracts high/low of the last Asian session from 15M/5M data.
        """
        if df.empty: return None
        # Get start/end of last Asian session
        # For simplicity, we look back at the most recent block between START and END
        asian_data = df[(df.index.time >= time(ASIAN_SESSION_START, 0)) & 
                        (df.index.time < time(ASIAN_SESSION_END, 0))]
        
        if asian_data.empty: return None
        
        # Take the most recent continuous block (today or yesterday)
        last_date = asian_data.index[-1].date()
        recent_block = asian_data[asian_data.index.date == last_date]
        
        return {
            'high': recent_block['high'].max(),
            'low': recent_block['low'].min()
        }
