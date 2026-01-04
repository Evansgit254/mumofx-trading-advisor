import yfinance as yf
import pandas as pd
from typing import Dict, Optional
from config.config import SYMBOLS, NARRATIVE_TF, STRUCTURE_TF, ENTRY_TF

class DataFetcher:
    @staticmethod
    def fetch_data(symbol: str, timeframe: str, period: str = "5d") -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=timeframe)
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
            print(f"Error fetching {timeframe} data for {symbol}: {e}")
            return None

    @staticmethod
    def fetch_range(symbol: str, timeframe: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol within a date range.
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
        Fetches multi-timeframe data for all symbols.
        """
        results = {}
        for symbol in symbols:
            # Narrative (1H) - Needs more history for 200 EMA
            h1_data = DataFetcher.fetch_data(symbol, NARRATIVE_TF, period="1mo")
            # Structure (15M)
            m15_data = DataFetcher.fetch_data(symbol, STRUCTURE_TF, period="8d")
            # Entry (5M)
            m5_data = DataFetcher.fetch_data(symbol, ENTRY_TF, period="5d")
            
            if h1_data is not None and m15_data is not None and m5_data is not None:
                results[symbol] = {
                    'h1': h1_data,
                    'm15': m15_data,
                    'm5': m5_data
                }
        return results
