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

class PriceActionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.ai_grader = AIGrader()
    
    def get_id(self) -> str:
        return "price_action_specialist"

    def get_name(self) -> str:
        return "Price Action Specialist"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        try:
            m5_df = data['m5']
            m15_df = data['m15']
            if len(m5_df) < 50: return None
            
            # --- V14.0 Performance: Read pre-calculated regime ---
            regime = m15_df.iloc[-1].get('regime', 'RANGING')
            if regime != "RANGING":
                return None

            latest = m5_df.iloc[-1]
            prev = m5_df.iloc[-2]
            
            # 1. Trend Filter (EMA 50 alignment)
            ema_50 = latest.get('ema_50')
            if ema_50 is None: return None
            
            trend = "BULLISH" if latest['close'] > ema_50 else "BEARISH"
            
            # 2. Pattern Detection: Pin Bar (Hammer)
            body = abs(latest['close'] - latest['open'])
            range_val = latest['high'] - latest['low']
            if range_val == 0: return None
            
            is_pin_bar = False
            direction = None
            
            # Bullish Pin Bar
            if trend == "BULLISH" and (latest['low'] < ema_50) and (latest['close'] > ema_50):
                lower_wick = min(latest['open'], latest['close']) - latest['low']
                if lower_wick > (range_val * 0.6) and body < (range_val * 0.3):
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
            
            if not direction:
                return None

            # 4. Filter: High-Quality Price Action Only
            rsi = latest.get('rsi')
            atr = latest.get('atr')
            if rsi is None or atr is None: return None
            
            # Stricter Filters: - V14.0 Performance Optimization
            atr_avg = latest.get('atr_ma_20', 0)
            if atr_avg == 0: return None
            
            # Stricter Filters: 
            if direction == "BUY" and (rsi < 45 or rsi > 65): return None
            if direction == "SELL" and (rsi > 55 or rsi < 35): return None
            if atr < (atr_avg * 0.9): return None

            # 5. Global Filter: Macro Bias
            macro_bias = MacroFilter.get_macro_bias(market_context)
            if not MacroFilter.is_macro_safe(symbol, direction, macro_bias):
                return None

            # 6. Session Filter
            if not SessionFilter.is_valid_session(check_time=m5_df.index[-1]):
                return None

            # --- V13.0 AI Setup Grader (Neural Shield) ---
            setup_data = {
                'symbol': symbol,
                'strategy_id': self.get_id(),
                'direction': direction,
                'regime': regime,
                'rsi': rsi,
                'adr_status': "Normal",
                'macro_bias': str(macro_bias),
                'va_status': "N/A"
            }
            ai_score = await self.ai_grader.get_score(setup_data)
            
            # PA requires very high AI validation due to counter-trend risk
            if ai_score < 7.0:
                return None

            # Calculation
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
                'confidence': ai_score, # Baseline
                'risk_details': risk_details,
                'session': f"Range {regime} Reversal"
            }
        except Exception as e:
            # print(f"🔥 PriceAction CRASH [{symbol}]: {e}")
            # traceback.print_exc()
            return None
