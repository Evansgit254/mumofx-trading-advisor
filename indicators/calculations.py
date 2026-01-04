import pandas as pd
import pandas_ta as ta
from config.config import EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD, ATR_AVG_PERIOD, EMA_TREND

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
