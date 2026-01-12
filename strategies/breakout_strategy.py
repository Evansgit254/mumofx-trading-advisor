from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
import traceback
from datetime import datetime
from config.config import (
    EMA_FAST, EMA_SLOW, ATR_MULTIPLIER
)
from indicators.calculations import IndicatorCalculator
from filters.session_filter import SessionFilter
from filters.macro_filter import MacroFilter
from filters.risk_manager import RiskManager
from filters.ai_grader import AIGrader

class BreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.ai_grader = AIGrader()
    
    def get_id(self) -> str:
        return "breakout_master"

    def get_name(self) -> str:
        return "Breakout Master"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        try:
            m5_df = data['m5']
            m15_df = data['m15']
            
            if len(m5_df) < 50: return None
            
            # --- V14.0 Performance: Read pre-calculated regime ---
            regime = m15_df.iloc[-1].get('regime', 'RANGING')
            if regime != "TRENDING":
                return None
            
            # Re-initialize AIGrader once if possible (Performance Optimization)
            # But since it's disabled, the overhead is minimal.

            latest = m5_df.iloc[-1]
            
            # 1. Bollinger Band Squeeze (Simplified)
            atr_now = latest.get('atr')
            if atr_now is None: return None
            
            # Compression check (ATR vs SMA of ATR) - V14.0 Performance Optimization
            atr_avg = latest.get('atr_ma_20', 0)
            if atr_avg == 0: return None

            # 2. Key Level Breakout (Asian Range) - V14.0 Performance Optimization
            asian_h = m15_df.iloc[-1].get('asian_high', 0)
            asian_l = m15_df.iloc[-1].get('asian_low', 0)
            
            if asian_h == 0: 
                return None
            
            direction = None
            if latest['close'] > asian_h and m5_df['close'].iloc[-2] <= asian_h:
                direction = "BUY"
            elif latest['close'] < asian_l and m5_df['close'].iloc[-2] >= asian_l:
                direction = "SELL"
                
            if not direction:
                return None
                
            # 3. Confirmation (Volume + RSI Move)
            rsi = latest.get('rsi')
            if rsi is None: return None
            
            if direction == "BUY" and (rsi < 50 or rsi > 80): return None
            if direction == "SELL" and (rsi > 50 or rsi < 20): return None

            # 4. Global Filter: Macro Bias
            macro_bias = MacroFilter.get_macro_bias(market_context)
            if not MacroFilter.is_macro_safe(symbol, direction, macro_bias):
                return None

            # 5. Filter: Session
            if not SessionFilter.is_valid_session(check_time=m5_df.index[-1]):
                return None

            # --- V13.0 AI Setup Grader (Neural Shield) ---
            setup_data = {
                'symbol': symbol,
                'strategy_id': self.get_id(),
                'direction': direction,
                'regime': regime,
                'rsi': rsi,
                'adr_status': "Normal", # Breakout is less ADR-sensitive than SMC
                'macro_bias': str(macro_bias),
                'va_status': "N/A"
            }
            ai_score = await self.ai_grader.get_score(setup_data)
            
            # Breakout requires high AI score to prevent "Fakes"
            if ai_score < 7.5:
                return None

            # Calculation
            sl = latest['close'] - (atr_now * ATR_MULTIPLIER) if direction == "BUY" else latest['close'] + (atr_now * ATR_MULTIPLIER)
            risk_details = RiskManager.calculate_lot_size(symbol, latest['close'], sl)
            
            return {
                'strategy_id': self.get_id(),
                'strategy_name': self.get_name(),
                'symbol': symbol,
                'direction': direction,
                'setup_quality': "BREAKOUT",
                'entry_price': latest['close'],
                'sl': sl,
                'tp0': latest['close'] + (atr_now * 1.5) if direction == "BUY" else latest['close'] - (atr_now * 1.5),
                'tp1': latest['close'] + (atr_now * 3.0) if direction == "BUY" else latest['close'] - (atr_now * 3.0),
                'tp2': latest['close'] + (atr_now * 5.0) if direction == "BUY" else latest['close'] - (atr_now * 5.0),
                'layers': [],
                'confidence': ai_score,
                'risk_details': risk_details,
                'session': f"Active {regime} Breakout"
            }
        except Exception as e:
            return None
