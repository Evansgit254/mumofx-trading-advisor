import yfinance as yf
import pandas as pd
from typing import Dict, Optional
from config.config import SYMBOLS, NARRATIVE_TF, STRUCTURE_TF, ENTRY_TF, INSTITUTIONAL_TF
from indicators.calculations import IndicatorCalculator

class DataFetcher:
    @staticmethod
    def fetch_data(symbol: str, timeframe: str, period: str = "5d") -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol with exponential backoff.
        """
        import time
        max_retries = 3
        backoff = 2
        
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=timeframe)
                
                if df is None or df.empty:
                    if attempt < max_retries - 1:
                        time.sleep(backoff ** attempt)
                        continue
                    return None
                
                df = df.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                # Check for empty index before conversion
                if df.index is None or len(df.index) == 0:
                    return None
                    
                df.index = df.index.tz_convert("UTC")
                return df
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Attempt {attempt+1} failed for {symbol} ({timeframe}): {e}. Retrying...")
                    time.sleep(backoff ** attempt)
                    continue
                print(f"❌ Error fetching {timeframe} data for {symbol}: {e}")
                return None
        return None

    @staticmethod
    def fetch_range(symbol: str, timeframe: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol within a date range with retries.
        """
        import time
        max_retries = 3
        backoff = 2
        
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start, end=end, interval=timeframe)
                
                if df is None or df.empty:
                    if attempt < max_retries - 1:
                        time.sleep(backoff ** attempt)
                        continue
                    return None
                
                df = df.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low', 
                    'Close': 'close', 
                    'Volume': 'volume'
                })
                if df.index is None or len(df.index) == 0:
                    return None
                    
                df.index = df.index.tz_convert("UTC")
                return df
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff ** attempt)
                    continue
                print(f"❌ Error fetching range for {symbol}: {e}")
                return None
        return None

    @staticmethod
    async def fetch_data_async(symbol: str, timeframe: str, period: str = "5d") -> Optional[pd.DataFrame]:
        """Asynchronous wrapper for fetch_data using threads."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, DataFetcher.fetch_data, symbol, timeframe, period)

    @staticmethod
    async def get_latest_data(symbols: list = SYMBOLS) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Fetches multi-timeframe data for all symbols concurrently.
        """
        from config.config import DXY_SYMBOL, TNX_SYMBOL
        import asyncio
        
        results = {}
        
        # 1. Prepare Fetch Tasks
        tasks = []
        task_info = []

        # Macro Narrative
        tasks.append(DataFetcher.fetch_data_async(DXY_SYMBOL, "1h", period="10d"))
        task_info.append(('DXY', 'h1'))
        
        tasks.append(DataFetcher.fetch_data_async(TNX_SYMBOL, "1h", period="10d"))
        task_info.append(('^TNX', 'h1'))

        for symbol in symbols:
            # Narrative (1H)
            tasks.append(DataFetcher.fetch_data_async(symbol, NARRATIVE_TF, period="1mo"))
            task_info.append((symbol, 'h1'))
            # Structure (15M)
            tasks.append(DataFetcher.fetch_data_async(symbol, STRUCTURE_TF, period="8d"))
            task_info.append((symbol, 'm15'))
            # Entry (5M)
            tasks.append(DataFetcher.fetch_data_async(symbol, ENTRY_TF, period="5d"))
            task_info.append((symbol, 'm5'))
            # Institutional (4H)
            tasks.append(DataFetcher.fetch_data_async(symbol, INSTITUTIONAL_TF, period="3mo"))
            task_info.append((symbol, 'h4'))

        # 2. Execute Tasks Concurrently
        fetched_dfs = await asyncio.gather(*tasks)

        # 3. Organize Results
        for (symbol, tf), df in zip(task_info, fetched_dfs):
            if df is None or df.empty:
                continue
            
            if symbol == 'DXY':
                results['DXY'] = IndicatorCalculator.add_indicators(df, "h1")
                continue
                
            if symbol == '^TNX':
                results['^TNX'] = IndicatorCalculator.add_indicators(df, "h1")
                continue

            if symbol not in results:
                results[symbol] = {}
            results[symbol][tf] = df

        # 4. Final Verification (Ensure all TFs present)
        final_results = {}
        if 'DXY' in results:
            final_results['DXY'] = results['DXY']
            
        if '^TNX' in results:
            final_results['^TNX'] = results['^TNX']
            
        for symbol in symbols:
            s_data = results.get(symbol, {})
            if 'h1' in s_data and 'm15' in s_data and 'm5' in s_data and 'h4' in s_data:
                final_results[symbol] = s_data
                
        return final_results
