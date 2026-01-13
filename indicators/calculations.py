import pandas as pd
import pandas_ta_classic as ta
from config.config import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD, ATR_AVG_PERIOD, 
    EMA_TREND, ADR_PERIOD, ASIAN_SESSION_START, ASIAN_SESSION_END,
    POC_LOOKBACK, ASIAN_RANGE_MIN_PIPS
)
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
        
        df[f'ema_{EMA_TREND}'] = ta.ema(df['close'], length=EMA_TREND)
        df['ema_20'] = ta.ema(df['close'], length=20)

        # RSI
        df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)

        # ATR
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD)
        
        # ATR Average for volatility filter
        df['atr_avg'] = df['atr'].rolling(window=ATR_AVG_PERIOD).mean()
        
        # ADR (Average Daily Range) - Only for H1 as it's the anchor TF for daily range
        if timeframe == "h1":
            df['adr'] = IndicatorCalculator.calculate_adr(df)
            
        if timeframe in ["15m", "5m", "m15", "m5"]:
            ar = IndicatorCalculator.calculate_asian_range(df)
            df['asian_high'] = ar['asian_high']
            df['asian_low'] = ar['asian_low']
            
            # V14.0 Performance: Structural Lookbacks (36 bars for SMC)
            df['prev_high_36'] = df['high'].shift(1).rolling(36).max()
            df['prev_low_36'] = df['low'].shift(1).rolling(36).min()
            
            # ATR Smoothing for Breakout thresholds
            df['atr_ma_20'] = df['atr'].rolling(20).mean()
        
        if timeframe == "h4":
            h4_lvls = IndicatorCalculator.calculate_h4_levels(df)
            df['h4_high'] = h4_lvls['h4_high']
            df['h4_low'] = h4_lvls['h4_low']
            
        # V14.0 Performance: Value Area (Vectorized)
        va = IndicatorCalculator.calculate_value_area_rolling(df)
        df['vah'] = va['vah']
        df['val'] = va['val']
        df['poc'] = va['poc']
        
        # V14.0 Vectorized Regime Detection
        # Calculate slope vectorized
        ema_trend_col = f'ema_{EMA_TREND}'
        df['ema_slope'] = ((df[ema_trend_col] - df[ema_trend_col].shift(3)) / df[ema_trend_col].shift(3)) * 100
        
        df['vol_ratio'] = df['atr'] / df['atr'].rolling(50).mean()
        
        # Default to RANGING
        df['regime'] = "RANGING"
        
        # Vectorized assignments
        df.loc[(df['vol_ratio'] > 1.2) & (df['ema_slope'].abs() > 0.05), 'regime'] = "TRENDING"
        df.loc[(df['vol_ratio'] < 0.8), 'regime'] = "CHOPPY"
        df.loc[(df['regime'] == "RANGING") & (df['vol_ratio'] > 1.5), 'regime'] = "CHOPPY" # Extra safety for ultra-vol

        # V14.0 Performance: Vectorized Structure
        df = IndicatorCalculator.get_market_structure(df)

        return df

    @staticmethod
    def get_market_structure(df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify FVGs and BOS in a vectorized way using rolling windows.
        """
        # Bullish FVG: Low[0] > High[-2]
        is_bull_fvg = (df['low'] > df['high'].shift(2))
        df['fvg_bullish'] = is_bull_fvg.rolling(10).max().fillna(0).astype(bool)
        
        # Bearish FVG: High[0] < Low[-2]
        is_bear_fvg = (df['high'] < df['low'].shift(2))
        df['fvg_bearish'] = is_bear_fvg.rolling(10).max().fillna(0).astype(bool)
        
        # BOS (Break of Structure) - Simplified vectorized logic
        # Buy BOS: Close > High of last 10 bars (Rolling 12 for SMC match)
        is_bos_buy = (df['close'] > df['high'].shift(1).rolling(10).max())
        df['bos_buy'] = is_bos_buy.rolling(12).max().fillna(0).astype(bool)
        
        is_bos_sell = (df['close'] < df['low'].shift(1).rolling(10).min())
        df['bos_sell'] = is_bos_sell.rolling(12).max().fillna(0).astype(bool)
        
        return df

    @staticmethod
    def calculate_adr(h1_df: pd.DataFrame) -> pd.Series:
        """
        Calculates the Average Daily Range (High - Low) from H1 data in a vectorized way.
        """
        if h1_df.empty: return pd.Series(index=h1_df.index, data=0.0)
        
        # Calculate daily ranges
        daily_high = h1_df['high'].resample('D').max()
        daily_low = h1_df['low'].resample('D').min()
        daily_range = daily_high - daily_low
        
        # Calculate moving average of daily range
        adr_ma = daily_range.rolling(window=ADR_PERIOD).mean()
        
        # Reindex back to original timeframe for easy lookup
        return adr_ma.reindex(h1_df.index).ffill().fillna(0.0)

    @staticmethod
    def calculate_asian_range(df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculates Asian high/low for every bar vectorized.
        """
        if df.empty: return pd.DataFrame(index=df.index, data={'asian_high': 0, 'asian_low': 0})
        
        # Filter for Asian session times
        is_asian = (df.index.time >= time(ASIAN_SESSION_START, 0)) & (df.index.time < time(ASIAN_SESSION_END, 0))
        
        # Group by day and get min/max
        asian_days = df[is_asian].resample('D').agg({'high': 'max', 'low': 'min'})
        asian_days.columns = ['asian_high', 'asian_low']
        
        # Forward fill to all bars of the day
        return asian_days.reindex(df.index).ffill().fillna(0.0)

    @staticmethod
    def calculate_poc(df: pd.DataFrame) -> float:
        """
        Calculates the Point of Control (POC) - price level with highest volume.
        Uses POC_LOOKBACK bars.
        """
        if df.empty: return 0.0
        
        subset = df.tail(POC_LOOKBACK).copy()
        if subset.empty: return 0.0
        
        # Create price bins (50 bins across the range)
        price_min = subset['low'].min()
        price_max = subset['high'].max()
        if price_min == price_max: return price_min
        
        bins = pd.cut(subset['close'], bins=50)
        volume_profile = subset.groupby(bins, observed=True)['volume'].sum()
        
        if volume_profile.empty: return subset['close'].iloc[-1]
        
        # Get the middle price of the winning bin
        winning_bin = volume_profile.idxmax()
        return winning_bin.mid

    @staticmethod
    def calculate_ema_slope(df: pd.DataFrame, ema_col: str) -> float:
        """
        Calculates the normalized velocity (slope) of an EMA.
        Returns % change over the last 3 bars.
        """
        if df.empty or ema_col not in df.columns: return 0.0
        
        subset = df[ema_col].tail(3)
        if len(subset) < 3: return 0.0
        
        start_val = subset.iloc[0]
        end_val = subset.iloc[-1]
        
        if start_val == 0: return 0.0
        
        # Normalized slope in % change
        slope = ((end_val - start_val) / start_val) * 100
        return round(slope, 4)

    @staticmethod
    def get_previous_candle_range(df: pd.DataFrame) -> dict:
        """
        Returns the high/low of the previous closed candle.
        """
        if df.empty or len(df) < 2: return None
        prev = df.iloc[-2]
        return {
            'high': prev['high'],
            'low': prev['low'],
            'close': prev['close'],
            'time': df.index[-2]
        }

    @staticmethod
    def calculate_h4_levels(df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculates H4 swing highs/lows for every bar vectorized.
        """
        if df.empty: return pd.DataFrame(index=df.index, data={'h4_high': 0, 'h4_low': 0})
        
        # Rolling min/max of last 10 candles
        res = pd.DataFrame(index=df.index)
        res['h4_high'] = df['high'].shift(1).rolling(10).max()
        res['h4_low'] = df['low'].shift(1).rolling(10).min()
        return res.ffill().fillna(0.0)

    @staticmethod
    def calculate_value_area_rolling(df: pd.DataFrame) -> pd.DataFrame:
        """
        Approximate Value Area using rolling standard deviation for speed.
        True volume profile is too slow for 30-day M5 backtest in a single pass.
        VAH = Mean + 1 StdDev, VAL = Mean - 1 StdDev (covers ~68% of price action).
        """
        res = pd.DataFrame(index=df.index)
        rolling_mean = df['close'].rolling(100).mean()
        rolling_std = df['close'].rolling(100).std()
        
        res['vah'] = rolling_mean + rolling_std
        res['val'] = rolling_mean - rolling_std
        res['poc'] = rolling_mean
        return res.ffill().fillna(0.0)

    @staticmethod
    def detect_crt_phases(df: pd.DataFrame) -> dict:
        """
        Detects Candle Range Theory (PO3) phases: 
        Accumulation (Range), Manipulation (Sweep), Distribution (Expansion).
        """
        if df.empty or len(df) < 50: return {'phase': 'ACCUMULATION', 'manipulated': False}
        
        # 1. Detect Accumulation (Consolidation)
        lookback = 24
        subset = df.iloc[-(lookback+5):-5] 
        range_high = subset['high'].max()
        range_low = subset['low'].min()
        
        # 2. Detect Manipulation (Sweep of range)
        recent = df.tail(5)
        manip_buy = (recent['low'] < range_low).any() and (recent['close'] > range_low).any()
        manip_sell = (recent['high'] > range_high).any() and (recent['close'] < range_high).any()
        
        # 3. Detect Distribution (Directional expansion)
        latest_close = df.iloc[-1]['close']
        latest_open = df.iloc[-5]['open'] 
        
        is_expansion_up = latest_close > latest_open and latest_close > range_high
        is_expansion_down = latest_close < latest_open and latest_close < range_low
        
        phase = "ACCUMULATION"
        score_bonus = 0
        if manip_buy and is_expansion_up:
            phase = "DISTRIBUTION_LONG"
            score_bonus = 1.5
        elif manip_sell and is_expansion_down:
            phase = "DISTRIBUTION_SHORT"
            score_bonus = 1.5
            
        return {
            'phase': phase,
            'range_high': range_high,
            'range_low': range_low,
            'manipulated': manip_buy or manip_sell,
            'score_bonus': score_bonus
        }

    @staticmethod
    def detect_bos(df: pd.DataFrame, direction: str, lookback: int = 5) -> bool:
        """
        Detects if a Break of Structure (BOS) occurred within the last 'lookback' bars.
        Used for entry confirmation after a sweep (V12.0).
        """
        if len(df) < 20: return False
        
        # Check if ANY of the last 'lookback' bars broke the previous structure
        for i in range(1, lookback + 1):
            idx = -i
            if abs(idx) >= len(df): break
            
            # Structure high/low BEFORE that specific candle
            hist_subset = df.iloc[:idx].tail(10)
            if hist_subset.empty: continue
            
            recent_max = hist_subset['high'].max()
            recent_min = hist_subset['low'].min()
            
            curr_close = df.iloc[idx]['close']
            
            if direction == "BUY" and curr_close > recent_max:
                return True
            if direction == "SELL" and curr_close < recent_min:
                return True
                
        return False

    @staticmethod
    def get_market_regime(df: pd.DataFrame) -> str:
        """
        Detects the current market regime based on volatility and trend.
        Returns: 'TRENDING', 'RANGING', or 'CHOPPY'
        """
        if len(df) < 50: return "CHOPPY"
        
        # 1. Volatility check (Current ATR vs 50-period average)
        atr_now = df.iloc[-1].get('atr')
        atr_avg = df['atr'].rolling(50).mean().iloc[-1]
        
        if atr_now is None or atr_avg is None: return "CHOPPY"
        
        vol_ratio = atr_now / atr_avg if atr_avg != 0 else 1
        
        # 2. Trendiness check (EMA Slope)
        slope = IndicatorCalculator.calculate_ema_slope(df, f'ema_{EMA_TREND}')
        
        # 3. Decision Logic
        # Highly volatile + slanted EMA = Trending
        if vol_ratio > 1.2 and abs(slope) > 0.05:
            return "TRENDING"
        # Normal volatility + flat EMA = Ranging
        elif 0.8 <= vol_ratio <= 1.5 and abs(slope) <= 0.05:
            return "RANGING"
        # Low volatility or extremely flat = Choppy (Avoid)
        elif vol_ratio < 0.8:
            return "CHOPPY"
            
        return "RANGING" # Default to Ranging
