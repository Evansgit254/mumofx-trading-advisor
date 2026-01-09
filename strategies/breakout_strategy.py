from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from datetime import datetime
from config.config import (
    EMA_FAST, EMA_SLOW, ATR_MULTIPLIER
)
from indicators.calculations import IndicatorCalculator
from filters.session_filter import SessionFilter
from filters.risk_manager import RiskManager

class BreakoutStrategy(BaseStrategy):
    def get_id(self) -> str:
        return "breakout_master"

    def get_name(self) -> str:
        return "Breakout Master"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        m5_df = data['m5']
        m15_df = data['m15']
        
        if len(m5_df) < 50: return None
        
        latest = m5_df.iloc[-1]
        
        # 1. Bollinger Band Squeeze (Simplified)
        # Check if ATR is below average (compression)
        atr_now = latest['atr']
        atr_avg = m5_df['atr'].rolling(20).mean().iloc[-1]
        
        if atr_now > atr_avg * 0.8: # Not a squeeze strictly, but check for range breakout
            pass

        # 2. Key Level Breakout (Asian Range)
        asian_range = IndicatorCalculator.get_asian_range(m15_df)
        if not asian_range: return None
        
        direction = None
        if latest['close'] > asian_range['high'] and m5_df['close'].iloc[-2] <= asian_range['high']:
            direction = "BUY"
        elif latest['close'] < asian_range['low'] and m5_df['close'].iloc[-2] >= asian_range['low']:
            direction = "SELL"
            
        if not direction:
            return None
            
        # 3. Confirmation (Volume + RSI Move)
        # Ensure RSI is not overextended and show momentum
        rsi = latest['rsi']
        if direction == "BUY" and (rsi < 50 or rsi > 70): return None
        if direction == "SELL" and (rsi > 50 or rsi < 30): return None

        # 4. Filter: Only during specific high-volatility sessions
        if not SessionFilter.is_valid_session():
            return None

        # 5. Calculation
        atr = latest['atr']
        sl = latest['close'] - (atr * ATR_MULTIPLIER) if direction == "BUY" else latest['close'] + (atr * ATR_MULTIPLIER)
        risk_details = RiskManager.calculate_lot_size(symbol, latest['close'], sl)
        
        # Suggestion Score (Static for now, will be dynamic in V11.0)
        confidence = 7.5
        
        return {
            'strategy_id': self.get_id(),
            'strategy_name': self.get_name(),
            'symbol': symbol,
            'direction': direction,
            'setup_quality': "BREAKOUT",
            'entry_price': latest['close'],
            'sl': sl,
            'tp0': latest['close'] + (atr * 1.5) if direction == "BUY" else latest['close'] - (atr * 1.5),
            'tp1': latest['close'] + (atr * 3.0) if direction == "BUY" else latest['close'] - (atr * 3.0),
            'tp2': latest['close'] + (atr * 5.0) if direction == "BUY" else latest['close'] - (atr * 5.0),
            'layers': [], # Breakouts usually don't layer the same way
            'confidence': confidence,
            'risk_details': risk_details,
            'session': "Active Breakout"
        }
