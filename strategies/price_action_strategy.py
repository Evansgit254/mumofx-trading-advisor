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

class PriceActionStrategy(BaseStrategy):
    def get_id(self) -> str:
        return "price_action_specialist"

    def get_name(self) -> str:
        return "Price Action Specialist"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        m5_df = data['m5']
        if len(m5_df) < 50: return None
        
        latest = m5_df.iloc[-1]
        prev = m5_df.iloc[-2]
        
        # 1. Trend Filter (EMA 50 alignment)
        ema_50 = m5_df.iloc[-1].get('ema_50', 0)
        if ema_50 == 0: return None
        
        trend = "BULLISH" if latest['close'] > ema_50 else "BEARISH"
        
        # 2. Pattern Detection: Pin Bar (Hammer)
        body = abs(latest['close'] - latest['open'])
        range = latest['high'] - latest['low']
        if range == 0: return None
        
        is_pin_bar = False
        direction = None
        
        # Bullish Pin Bar
        if trend == "BULLISH" and (latest['low'] < ema_50) and (latest['close'] > ema_50):
            lower_wick = min(latest['open'], latest['close']) - latest['low']
            if lower_wick > (range * 0.6) and body < (range * 0.3):
                is_pin_bar = True
                direction = "BUY"
        
        # 3. Pattern Detection: Engulfing
        if not is_pin_bar:
            if trend == "BULLISH" and latest['close'] > prev['high'] and latest['open'] < prev['low'] and latest['close'] > latest['open']:
                is_pin_bar = True # Reuse flag for simplicity
                direction = "BUY"
            elif trend == "BEARISH" and latest['close'] < prev['low'] and latest['open'] > prev['high'] and latest['close'] < latest['open']:
                is_pin_bar = True
                direction = "SELL"

        # 4. Filter: High-Quality Price Action Only
        rsi = latest['rsi']
        atr = latest['atr']
        atr_avg = m5_df['atr'].rolling(20).mean().iloc[-1]
        
        # Stricter Filters: 
        # - RSI must show momentum but not overbought/sold
        # - ATR must be expanding (Volatility)
        if direction == "BUY" and (rsi < 45 or rsi > 65): return None
        if direction == "SELL" and (rsi > 55 or rsi < 35): return None
        if atr < (atr_avg * 0.9): return None

        # 5. Session Filter
        if not SessionFilter.is_valid_session():
            return None

        # 5. Calculation
        atr = latest['atr']
        sl = latest['low'] - (0.5 * atr) if direction == "BUY" else latest['high'] + (0.5 * atr)
        risk_details = RiskManager.calculate_lot_size(symbol, latest['close'], sl)
        
        return {
            'strategy_id': self.get_id(),
            'strategy_name': self.get_name(),
            'symbol': symbol,
            'direction': direction,
            'setup_quality': "PRICE_ACTION",
            'entry_price': latest['close'],
            'sl': sl,
            'tp1': latest['close'] + (atr * 2.0) if direction == "BUY" else latest['close'] - (atr * 2.0),
            'tp2': latest['close'] + (atr * 4.0) if direction == "BUY" else latest['close'] - (atr * 4.0),
            'tp0': latest['close'] + (atr * 1.0) if direction == "BUY" else latest['close'] - (atr * 1.0),
            'layers': [],
            'confidence': 7.0, # Baseline
            'risk_details': risk_details,
            'session': "Trend Reversal"
        }
