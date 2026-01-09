from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
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
from audit.optimizer import AutoOptimizer

class SMCStrategy(BaseStrategy):
    def get_id(self) -> str:
        return "smc_institutional"

    def get_name(self) -> str:
        return "SMC Institutional"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        h1_df = data['h1']
        m15_df = data['m15']
        m5_df = data['m5']
        h4_df = data['h4']

        # 1. Indicators are already added by main loop
        
        # 2. H1 Trend Check
        h1_close = h1_df.iloc[-1]['close']
        h1_ema = h1_df.iloc[-1][f'ema_{EMA_TREND}']
        h1_trend = "BULLISH" if h1_close > h1_ema else "BEARISH"
        h1_dist = (h1_close - h1_ema) / h1_ema if h1_ema != 0 else 0

        # adaptive lookback
        now_hour = datetime.now().hour
        if 13 <= now_hour <= 21: lookback = 50
        elif 7 <= now_hour < 13: lookback = 35
        else: lookback = 21

        if symbol == "GC=F":
            lookback = 20 # Gold Specialist

        if len(m15_df) < lookback + 1: return None
        
        prev_high = m15_df['high'].iloc[-(lookback+1):-1].max()
        prev_low = m15_df['low'].iloc[-(lookback+1):-1].min()
        latest_high = m15_df['high'].iloc[-1]
        latest_low = m15_df['low'].iloc[-1]
        latest_close = m15_df['close'].iloc[-1]
        
        direction = None
        sweep_level = 0
        sweep_type = "M15_SWEEP"
        
        if latest_low < prev_low and latest_close > prev_low and h1_trend == "BULLISH":
            direction = "BUY"
            sweep_level = prev_low
        elif latest_high > prev_high and latest_close < prev_high and h1_trend == "BEARISH":
            direction = "SELL"
            sweep_level = prev_high

        if not direction:
            return None

        # 4H Level Alignment
        h4_levels = IndicatorCalculator.get_h4_levels(h4_df)
        h4_sweep = False
        if h4_levels:
            if direction == "BUY" and latest_low < h4_levels['prev_h4_low'] and latest_close > h4_levels['prev_h4_low']:
                h4_sweep = True
            elif direction == "SELL" and latest_high > h4_levels['prev_h4_high'] and latest_close < h4_levels['prev_h4_high']:
                h4_sweep = True
                
        crt_validation = CRTAnalyzer.validate_setup(m15_df, direction)
        fvgs = ImbalanceDetector.detect_fvg(m5_df)
        has_fvg = ImbalanceDetector.is_price_in_fvg(latest_close, fvgs, direction)
        if not has_fvg:
            m15_fvgs = ImbalanceDetector.detect_fvg(m15_df)
            has_fvg = ImbalanceDetector.is_price_in_fvg(latest_close, m15_fvgs, direction)
        
        displaced = DisplacementAnalyzer.is_displaced(m5_df, direction)
        entry = EntryLogic.check_pullback(m5_df, direction)
        
        # Filters
        is_news_safe = NewsFilter.is_news_safe(news_events, symbol)
        if symbol == "GC=F":
            is_session = 8 <= datetime.now().hour <= 21
        else:
            is_session = SessionFilter.is_valid_session()

        if not is_news_safe or not is_session:
            return None

        # Additional Quant Metrics
        adr = IndicatorCalculator.calculate_adr(h1_df)
        asian_range = IndicatorCalculator.get_asian_range(m15_df)
        
        today = h1_df.index[-1].date()
        today_data = h1_df[h1_df.index.date == today]
        current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
        
        adr_exhausted = False
        if adr > 0 and current_range >= (adr * 0.9): # standard threshold
            adr_exhausted = True
            
        asian_sweep = False
        asian_quality = False
        if asian_range:
            raw_range = asian_range['high'] - asian_range['low']
            pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
            min_pips = 20 if symbol == "GC=F" else ASIAN_RANGE_MIN_PIPS
            if pips >= min_pips:
                asian_quality = True
            if direction == "BUY" and latest_low < asian_range['low']:
                asian_sweep = True
            elif direction == "SELL" and latest_high > asian_range['high']:
                asian_sweep = True

        poc = IndicatorCalculator.calculate_poc(m5_df)
        atr = m5_df.iloc[-1]['atr']
        at_value = abs(latest_close - poc) <= (0.5 * atr)
        ema_slope = IndicatorCalculator.calculate_ema_slope(h1_df, f'ema_{EMA_TREND}')

        # Scoring
        score_details = {
            'h1_aligned': True,
            'sweep_type': sweep_type,
            'displaced': displaced,
            'pullback': entry is not None,
            'session': "Active",
            'volatile': VolatilityFilter.is_volatile(m5_df),
            'asian_sweep': asian_sweep,
            'asian_quality': asian_quality,
            'adr_exhausted': adr_exhausted,
            'at_value': at_value,
            'ema_slope': ema_slope,
            'h1_dist': h1_dist,
            'has_fvg': has_fvg,
            'h4_sweep': h4_sweep,
            'crt_bonus': crt_validation.get('score_bonus', 0),
            'crt_phase': crt_validation.get('phase', ''),
            'symbol': symbol,
            'direction': direction
        }
        
        confidence = ScoringEngine.calculate_score(score_details)
        threshold = GOLD_CONFIDENCE_THRESHOLD if symbol == "GC=F" else MIN_CONFIDENCE_SCORE
        
        if confidence >= threshold:
            setup_quality = "A+" if confidence >= 9.0 else "A" if confidence >= 8.5 else "B"
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
                'confidence': confidence,
                'risk_details': risk_details,
                'session': "Active",
                'h4_sweep': h4_sweep,
                'crt_phase': crt_validation.get('phase', 'ACC')
            }
        
        return None
