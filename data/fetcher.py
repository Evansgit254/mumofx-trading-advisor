import yfinance as yf
import pandas as pd
from typing import Dict, Optional
from config.config import SYMBOLS, BIAS_TF, ENTRY_TF

class DataFetcher:
    @staticmethod
    def fetch_data(symbol: str, timeframe: str, period: str = "5d") -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol.
        Timeframes: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=timeframe)
            if df.empty:
                return None
            
            # Ensure columns are standard
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            return df
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None

    @staticmethod
    def fetch_range(symbol: str, timeframe: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol within a date range.
        Format: YYYY-MM-DD
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=timeframe)
            if df.empty:
                return None
            
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low', 
                'Close': 'close', 
                'Volume': 'volume'
            })
            return df
        except Exception as e:
            print(f"Error fetching range for {symbol}: {e}")
            return None

    @staticmethod
    def get_latest_data(symbols: list = SYMBOLS) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Fetches M1 and M5 data for all symbols.
        """
        results = {}
        for symbol in symbols:
            m5_data = DataFetcher.fetch_data(symbol, BIAS_TF, period="5d")
            m1_data = DataFetcher.fetch_data(symbol, ENTRY_TF, period="2d")
            
            if m5_data is not None and m1_data is not None:
                results[symbol] = {
                    'm5': m5_data,
                    'm1': m1_data
                }
        return results
