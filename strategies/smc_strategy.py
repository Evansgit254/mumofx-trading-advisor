from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
import traceback
from datetime import datetime
from config.config import (
    MIN_CONFIDENCE_SCORE, 
    GOLD_CONFIDENCE_THRESHOLD,
    EMA_TREND,
    ASIAN_RANGE_MIN_PIPS
)
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from strategy.imbalance import ImbalanceDetector
from strategy.crt import CRTAnalyzer
from filters.session_filter import SessionFilter
from filters.volatility_filter import VolatilityFilter
from filters.news_filter import NewsFilter
from filters.risk_manager import RiskManager
from filters.macro_filter import MacroFilter
from filters.ai_grader import AIGrader
from filters.daily_bias import DailyBias
from audit.optimizer import AutoOptimizer

class SMCStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.ai_grader = AIGrader()  # V13: Initialize once, reuse for all signals
    
    def get_id(self) -> str:
        return "smc_institutional"

    def get_name(self) -> str:
        return "SMC Institutional"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        try:
            h1_df = data.get('h1')
            m15_df = data.get('m15')
            m5_df = data.get('m5')
            h4_df = data.get('h4')
            d1_df = data.get('d1')
            
            if h1_df is None or m15_df is None or m5_df is None: return None
            
            is_gold = symbol in ["GC=F", "XAUUSD=X"]

            # --- V14.0 Performance: Read pre-calculated regime ---
            regime = m15_df.iloc[-1].get('regime', 'RANGING')
            
            # Phase 6: Daily Bias Analysis (Chop Override)
            daily_analysis = DailyBias.analyze(d1_df) if d1_df is not None else {'bias': 'NEUTRAL', 'strength': 'WEAK'}
            
            # Gold Exception: Institutional sweeps often happen during "Choppy" consolidation
            # Daily Bias Override: Allow trading in Chop if Daily Trend is STRONG
            is_choppy = regime == "CHOPPY"
            daily_override = daily_analysis['strength'] == "STRONG"
            
            if is_choppy and not is_gold and not daily_override:
                return None
            
            # Higher Timeframe Trend (Narrative)
            h1_close = h1_df.iloc[-1]['close']
            h1_ema = h1_df.iloc[-1].get(f'ema_{EMA_TREND}')
            if h1_ema is None: return None
            
            h1_trend = "BULLISH" if h1_close > h1_ema else "BEARISH"
            h1_dist = (h1_close - h1_ema) / h1_ema if h1_ema != 0 else 0

            # adaptive lookback based on price time
            price_time = m5_df.index[-1]
            now_hour = price_time.hour
            if 13 <= now_hour <= 21: lookback = 50
            elif 7 <= now_hour < 13: lookback = 35
            else: lookback = 21

            if is_gold:
                lookback = 20 # Gold Specialist: 5 hours (Faster structure)

            if len(m15_df) < lookback + 5: 
                return None
            
            # V14.0 Performance: Read pre-calculated structural levels
            # Instead of on-the-fly max/min scans, we use 36-bar rolling columns
            # which were pre-processed in IndicatorCalculator.add_indicators
            prev_high = m15_df.iloc[-1].get('prev_high_36', 0)
            prev_low = m15_df.iloc[-1].get('prev_low_36', 0)
            
            if prev_high == 0 or prev_low == 0: return None
            
            # Check if M5 price is CURRENTLY sweeping that M15 level
            latest_high = m5_df['high'].iloc[-1]
            latest_low = m5_df['low'].iloc[-1]
            latest_close = m5_df['close'].iloc[-1]
            
            direction = None
            sweep_level = 0
            sweep_type = "HYBRID_SWEEP"
            
            # Current bar sweep
            if latest_low < prev_low and latest_close > prev_low:
                direction = "BUY"
                sweep_level = prev_low
            elif latest_high > prev_high and latest_close < prev_high:
                direction = "SELL"
                sweep_level = prev_high
            
            # If not current, check RECENT M5 bars for a sweep (Delayed Entry model)
            if not direction:
                for i in range(2, 20):
                    if i >= len(m5_df): break
                    c_low = m5_df['low'].iloc[-i]
                    c_high = m5_df['high'].iloc[-i]
                    c_close = m5_df['close'].iloc[-i]
                    if c_low < prev_low and c_close > prev_low:
                        direction = "BUY"
                        sweep_level = prev_low
                        break
                    elif c_high > prev_high and c_close < prev_high:
                        direction = "SELL"
                        sweep_level = prev_high
                        break

            if not direction:
                return None


                
            h1_aligned = (direction == "BUY" and h1_trend == "BULLISH") or (direction == "SELL" and h1_trend == "BEARISH")
            
            # 4H Level Alignment - V14.0 Performance Optimization
            h4_latest = h4_df.iloc[-1]
            h4_high = h4_latest.get('h4_high', 0)
            h4_low = h4_latest.get('h4_low', 0)
            
            h4_sweep = False
            if h4_low > 0:
                if direction == "BUY" and latest_low < h4_low and latest_close > h4_low:
                    h4_sweep = True
                elif direction == "SELL" and latest_high > h4_high and latest_close < h4_high:
                    h4_sweep = True
                    
            crt_validation = CRTAnalyzer.validate_setup(m15_df, direction)
            
            # Gold Exception: CRT can be strict, so use bonus if low confidence
            if is_gold and not crt_validation and not h1_aligned:
                 # Gold needs at least H1 alignment OR CRT
                 return None

            # FVGs - V14.0 Performance Optimization
            has_fvg = False
            if direction == "BUY":
                has_fvg = m5_df.iloc[-1].get('fvg_bullish', False) or m15_df.iloc[-1].get('fvg_bullish', False)
            elif direction == "SELL":
                has_fvg = m5_df.iloc[-1].get('fvg_bearish', False) or m15_df.iloc[-1].get('fvg_bearish', False)
            
            displaced = DisplacementAnalyzer.is_displaced(m5_df, direction)
            
            # BOS (Break of Structure) - V14.0 Performance Optimization
            bos_confirmed = False
            if direction == "BUY":
                bos_confirmed = m5_df.iloc[-1].get('bos_buy', False)
            elif direction == "SELL":
                bos_confirmed = m5_df.iloc[-1].get('bos_sell', False)
            
            # --- V14.0 Value Area: Read pre-calculated columns ---
            vah = m5_df.iloc[-1].get('vah', 0)
            val = m5_df.iloc[-1].get('val', 0)
            in_value = False
            if vah > 0:
                if direction == "BUY" and latest_close <= vah: in_value = True
                elif direction == "SELL" and latest_close >= val: in_value = True

            entry = EntryLogic.check_pullback(m5_df, direction)
            
            # Filters
            is_news_safe = NewsFilter.is_news_safe(news_events, symbol)
            
            # --- V12.0 Macro & Session ---
            macro_bias = MacroFilter.get_macro_bias(market_context)
            is_macro_safe = MacroFilter.is_macro_safe(symbol, direction, macro_bias)
            
            if is_gold:
                # Gold Optimization: Allow pre-London moves (07:00 UTC)
                is_session = 7 <= price_time.hour <= 21
            else:
                is_session = SessionFilter.is_valid_session(check_time=price_time)
                
            if not is_news_safe or not is_session:
                return None
            
            # Additional Quant Metrics (V14.0: Read pre-calculated ADR)
            adr = h1_df.iloc[-1].get('adr', 0.0)
            
            today = h1_df.index[-1].date()
            today_data = h1_df[h1_df.index.date == today]
            current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
            
            adr_exhausted = False
            if adr > 0 and current_range >= (adr * 0.9): 
                adr_exhausted = True
                
            # asian_range = IndicatorCalculator.get_asian_range(m15_df)
            asian_h = m15_df.iloc[-1].get('asian_high', 0)
            asian_l = m15_df.iloc[-1].get('asian_low', 0)
            
            asian_sweep = False
            asian_quality = False
            if asian_h > 0:
                raw_range = asian_h - asian_l
                pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
                
                # Gold Asian Range Optimization: 20 pips minimum
                min_pips = 20 if is_gold else ASIAN_RANGE_MIN_PIPS
                
                if pips >= min_pips:
                    asian_quality = True
                if direction == "BUY" and latest_low < asian_l:
                    asian_sweep = True
                elif direction == "SELL" and latest_high > asian_h:
                    asian_sweep = True

            poc = m5_df.iloc[-1].get('poc', 0)
            atr = m5_df.iloc[-1]['atr']
            ema_slope = IndicatorCalculator.calculate_ema_slope(h1_df, f'ema_{EMA_TREND}')

            # Scoring
            score_details = {
                'h1_aligned': h1_aligned,
                'macro_aligned': is_macro_safe,
                'sweep_type': sweep_type,
                'displaced': displaced,
                'pullback': entry is not None,
                'session': "Active",
                'volatile': VolatilityFilter.is_volatile(m5_df),
                'asian_sweep': asian_sweep,
                'asian_quality': asian_quality,
                'adr_exhausted': adr_exhausted,
                'at_value': in_value,
                'bos_confirmed': bos_confirmed,
                'ema_slope': ema_slope,
                'h1_dist': h1_dist,
                'has_fvg': has_fvg,
                'h4_sweep': h4_sweep,
                'crt_bonus': crt_validation.get('score_bonus', 0) if crt_validation else 0,
                'crt_phase': crt_validation.get('phase', '') if crt_validation else '',
                'symbol': symbol,
                'direction': direction,
                'daily_bias': daily_analysis['bias'],
                'daily_strength': daily_analysis['strength']
            }
            
            # Gold-DXY Inverse Correlation Filter
            if is_gold and market_context and 'DXY' in market_context:
                dxy_df = market_context.get('DXY')
                if dxy_df is not None and len(dxy_df) > 0:
                    dxy_close = dxy_df.iloc[-1]['close']
                    dxy_ema = dxy_df.iloc[-1].get('ema_100', dxy_close)
                    dxy_trend = "BULLISH" if dxy_close > dxy_ema else "BEARISH"
                    
                    # Gold typically moves INVERSE to DXY
                    divergence = (direction == "BUY" and dxy_trend == "BULLISH") or \
                                 (direction == "SELL" and dxy_trend == "BEARISH")
                    
                    if divergence:
                        score_details['confluence'] = f"⚠️ DXY Divergence ({dxy_trend})"
                        score_details['dxy_penalty'] = -0.5 # V15.2: Relaxed from -2.0
                    else:
                        if direction == "BUY":
                            score_details['confluence'] = "✅ DXY Weakness"
                        else:
                            score_details['confluence'] = "✅ DXY Strength"
                        score_details['dxy_bonus'] = 1.5
            
            confidence = ScoringEngine.calculate_score(score_details)
            
            # --- V13.0 AI Setup Grader (Neural Shield) ---
            setup_data = {
                'symbol': symbol,
                'strategy_id': self.get_id(),
                'direction': direction,
                'regime': regime,
                'rsi': m5_df.iloc[-1].get('rsi'),
                'adr_status': "Exhausted" if adr_exhausted else "Normal",
                'macro_bias': str(macro_bias),
                'va_status': "Inside" if in_value else "Outside"
            }
            ai_score = await self.ai_grader.get_score(setup_data)
            
            # Weight the AI score into the final confidence
            final_confidence = (confidence * 0.4) + (ai_score * 0.6)
            
            threshold = GOLD_CONFIDENCE_THRESHOLD if is_gold else MIN_CONFIDENCE_SCORE
            
            if final_confidence >= threshold:
                setup_quality = "A+" if final_confidence >= 9.0 else "A" if final_confidence >= 8.5 else "B"
                opt_mult = AutoOptimizer.get_multiplier_for_symbol(symbol)
                levels = EntryLogic.calculate_levels(m5_df, direction, sweep_level, atr, symbol=symbol, opt_mult=opt_mult)
                risk_details = RiskManager.calculate_lot_size(symbol, latest_close, levels['sl'])
                layers = RiskManager.calculate_layers(risk_details['lots'], latest_close, levels['sl'], direction, setup_quality)
                
                return {
                    'strategy_id': self.get_id(),
                    'strategy_name': self.get_name(),
                    'symbol': symbol,
                    'direction': direction,
                    'setup_quality': setup_quality,
                    'entry_price': latest_close,
                    'sl': levels['sl'],
                    'tp0': levels['tp0'],
                    'tp1': levels['tp1'],
                    'tp2': levels['tp2'],
                    'layers': layers,
                    'confidence': final_confidence,
                    'risk_details': risk_details,
                    'session': "Active",
                    'h4_sweep': h4_sweep,
                    'crt_phase': crt_validation.get('phase', 'ACC') if crt_validation else 'ACC'
                }
            
            return None

        except Exception as e:
            return None
