import asyncio
import pandas as pd
from datetime import datetime
from config.config import (
    SYMBOLS, 
    MIN_CONFIDENCE_SCORE, 
    NARRATIVE_TF, 
    STRUCTURE_TF, 
    ENTRY_TF,
    ADR_THRESHOLD_PERCENT,
    ASIAN_RANGE_MIN_PIPS,
    EMA_TREND
)
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
# V7.0 Quantum Shield - Optimized Parallel Pipeline
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from strategy.imbalance import ImbalanceDetector
from strategy.crt import CRTAnalyzer
from filters.session_filter import SessionFilter
from filters.volatility_filter import VolatilityFilter
from filters.news_filter import NewsFilter
from data.news_fetcher import NewsFetcher
from alerts.service import TelegramService
from ai.analyst import AIAnalyst
from filters.correlation import CorrelationAnalyzer
from filters.risk_manager import RiskManager
from tools.tv_renderer import TVChartRenderer
from audit.journal import SignalJournal

import joblib
import os

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def process_symbol(symbol: str, data: dict, news_events: list, ai_analyst: AIAnalyst, data_batch: dict) -> dict:
    h1_df = data['h1']
    m15_df = data['m15']
    m5_df = data['m5']
    h4_df = data['h4']

    # 1. Add Indicators to all timeframes
    h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
    m15_df = IndicatorCalculator.add_indicators(m15_df, "m15")
    m5_df = IndicatorCalculator.add_indicators(m5_df, "m5")

    # 2. V6.1 Simple H1 Trend Check
    h1_close = h1_df.iloc[-1]['close']
    h1_ema = h1_df.iloc[-1][f'ema_{EMA_TREND}']
    h1_trend_val = 1 if h1_close > h1_ema else -1
    h1_trend = "BULLISH" if h1_trend_val == 1 else "BEARISH"
    h1_dist = (h1_close - h1_ema) / h1_ema if h1_ema != 0 else 0

    # --- V7.0 OPTIMIZATION: Session-Adaptive Lookback ---
    now_hour = datetime.now().hour
    # NY (13-21): 50 bars, London (07-13): 35 bars, Asian (00-07): 21 bars
    if 13 <= now_hour <= 21: lookback = 50
    elif 7 <= now_hour < 13: lookback = 35
    else: lookback = 21
    
    # 2. Structure (15M) - Sweep detection
    m15_df = data['m15']
    if len(m15_df) < lookback + 1: 
        return None
    
    # Calculate previous high/low within adaptive window
    prev_high = m15_df['high'].iloc[-(lookback+1):-1].max()
    prev_low = m15_df['low'].iloc[-(lookback+1):-1].min()
    
    latest_high = m15_df['high'].iloc[-1]
    latest_low = m15_df['low'].iloc[-1]
    latest_close = m15_df['close'].iloc[-1]
    
    direction = None
    setup_tf = "M15"
    sweep_level = 0
    sweep_type = "M15_SWEEP"
    
    # Buy: latest low < prev_low AND latest close > prev_low
    if latest_low < prev_low and latest_close > prev_low and h1_trend == "BULLISH":
        direction = "BUY"
        sweep_level = prev_low
    # Sell: latest high > prev_high AND latest close < prev_high
    elif latest_high > prev_high and latest_close < prev_high and h1_trend == "BEARISH":
        direction = "SELL"
        sweep_level = prev_high

    if not direction:
        return None

    # --- V8.0 INTEGRATION: 4H Level Alignment & CRT ---
    h4_levels = IndicatorCalculator.get_h4_levels(h4_df)
    h4_sweep = False
    if h4_levels:
        if direction == "BUY" and latest_low < h4_levels['prev_h4_low'] and latest_close > h4_levels['prev_h4_low']:
            h4_sweep = True
        elif direction == "SELL" and latest_high > h4_levels['prev_h4_high'] and latest_close < h4_levels['prev_h4_high']:
            h4_sweep = True
            
    crt_validation = CRTAnalyzer.validate_setup(m15_df, direction)

    # --- V7.0 OPTIMIZATION: FVG Confluence ---
    m5_df = data['m5']
    fvgs = ImbalanceDetector.detect_fvg(m5_df)
    has_fvg = ImbalanceDetector.is_price_in_fvg(latest_close, fvgs, direction)
    
    # If no FVG on M5, check M15 for deeper institutional interest
    if not has_fvg:
        m15_fvgs = ImbalanceDetector.detect_fvg(m15_df)
        has_fvg = ImbalanceDetector.is_price_in_fvg(latest_close, m15_fvgs, direction)
    
    # 4. Displacement Confirmation (on Entry TF)
    displaced = DisplacementAnalyzer.is_displaced(m5_df, direction)
    
    # 5. Entry Logic (Pullback on M5)
    entry = EntryLogic.check_pullback(m5_df, direction)
    
    # 6. Filters
    session = SessionFilter.get_session_name()
    volatile = VolatilityFilter.is_volatile(m5_df)
    atr_status = VolatilityFilter.get_atr_status(m5_df)
    is_news_safe = NewsFilter.is_news_safe(news_events, symbol)
    
    if not is_news_safe:
        return None

    # 7. V4.0 Ultra-Quant Analysis
    adr = IndicatorCalculator.calculate_adr(h1_df)
    asian_range = IndicatorCalculator.get_asian_range(m15_df)
    
    # Calculate Current Daily Range
    today = h1_df.index[-1].date()
    today_data = h1_df[h1_df.index.date == today]
    
    current_range = 0
    if not today_data.empty:
        current_range = today_data['high'].max() - today_data['low'].min()
    
    adr_exhausted = False
    if adr > 0 and current_range >= (adr * ADR_THRESHOLD_PERCENT):
        adr_exhausted = True
        
    asian_sweep = False
    asian_quality = False
    if asian_range:
        # Calculate Pips for quality check
        raw_range = asian_range['high'] - asian_range['low']
        pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
        
        # Gold Specialist: 20 pips required for quality, others 15
        min_pips = 20 if symbol == "GC=F" else ASIAN_RANGE_MIN_PIPS
        if pips >= min_pips:
            asian_quality = True
            
        if direction == "BUY" and m5_df.iloc[-1]['low'] < asian_range['low']:
            asian_sweep = True
        elif direction == "SELL" and m5_df.iloc[-1]['high'] > asian_range['high']:
            asian_sweep = True

    # 8. V5.0 Hyper-Quant: Volume Profile (POC)
    poc = IndicatorCalculator.calculate_poc(m5_df)
    atr = m5_df.iloc[-1]['atr']
    at_value = abs(m5_df.iloc[-1]['close'] - poc) <= (0.5 * atr) # Within 0.5 ATR of Value

    # 10. V6.0 Anti-Trap: EMA Velocity (Slope)
    ema_slope = IndicatorCalculator.calculate_ema_slope(h1_df, f'ema_{EMA_TREND}')

    # 12. Scoring
    score_details = {
        'h1_aligned': True,
        'sweep_type': sweep_type,
        'displaced': displaced,
        'pullback': entry is not None,
        'session': session,
        'volatile': volatile,
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

    # 12. AI Market Intelligence (Confirmation)
    ai_result = {"valid": True, "institutional_logic": "Standard liquidity alignment."}
    
    # Gold Specialist: Lower AI trigger to 8.2 for GC=F
    ai_threshold = 8.2 if "GC=F" in symbol else 8.5
    
    if confidence >= ai_threshold:
        ai_result = await ai_analyst.validate_signal({
            'pair': symbol,
            'direction': direction,
            'h1_trend': h1_trend,
            'setup_tf': sweep_type,
            'liquidity_event': f'{sweep_type} at {sweep_level:.5f}',
            'confidence': confidence
        })
        
    if not ai_result.get('valid', True):
        print(f"AI rejected {symbol} setup: {ai_result.get('institutional_logic')}")
        return None

    # 9. ML Probability (Local Model)
    win_prob = 0.5 # Default
    if ML_MODEL:
        try:
            # Features: ['rsi', 'body_ratio', 'atr_norm', 'displaced', 'h1_trend']
            rsi = m15_df.iloc[-1]['rsi']
            latest = m15_df.iloc[-1]
            body_ratio = abs(latest['close'] - latest['open']) / (latest['high'] - latest['low']) if (latest['high'] - latest['low']) != 0 else 0
            atr_norm = latest['atr'] / latest['close']
            h1_trend_val = 1 if h1_trend == "BULLISH" else -1
            displaced_val = 1 if displaced else 0
            
            features = pd.DataFrame([[rsi, body_ratio, atr_norm, displaced_val, h1_trend_val]], 
                                    columns=['rsi', 'body_ratio', 'atr_norm', 'displaced', 'h1_trend'])
            win_prob = ML_MODEL.predict_proba(features)[0][1]
        except Exception as e:
            print(f"ML Scoring Error: {e}")

    # 10. Gold Specialist: DXY Confluence
    confluence_text = ""
    if "GC=F" in symbol and 'DXY' in data_batch:
        dxy_df = data_batch['DXY']
        # V6.1: Simple DXY trend check
        dxy_close = dxy_df.iloc[-1]['close']
        dxy_ema = dxy_df.iloc[-1].get('ema_100', 0)
        dxy_trend = "BULLISH" if dxy_close > dxy_ema else "BEARISH"
        dxy_bias = "BULLISH" if dxy_trend == "BULLISH" else "BEARISH"
        
        # Gold and DXY are INVERSELY correlated
        if direction == "BUY" and dxy_bias == "BEARISH":
            confluence_text = "📊 *DXY Confluence:* ✅ Inverse Dollar weakness detected."
        elif direction == "SELL" and dxy_bias == "BULLISH":
            confluence_text = "📊 *DXY Confluence:* ✅ Inverse Dollar strength detected."
        else:
            confluence_text = "📊 *DXY Confluence:* ⚠️ Divergence detected."

    # 11. Alerting
    if confidence >= MIN_CONFIDENCE_SCORE:
        from audit.optimizer import AutoOptimizer
        setup_quality = "A+" if confidence >= 9.0 else "A" if confidence >= 8.5 else "B"
        
        # Self-Optimization: Get dynamic multiplier
        opt_mult = AutoOptimizer.get_multiplier_for_symbol(symbol)
        
        levels = EntryLogic.calculate_levels(m5_df, direction, sweep_level, atr, symbol=symbol, opt_mult=opt_mult)
        risk_details = RiskManager.calculate_lot_size(symbol, m5_df.iloc[-1]['close'], levels['sl'])
        layers = RiskManager.calculate_layers(risk_details['lots'], m5_df.iloc[-1]['close'], levels['sl'], direction, setup_quality)
        
        # News Warning
        news_warning = ""
        upcoming_news = NewsFilter.get_upcoming_events(news_events, symbol)
        if upcoming_news:
            news_warning = "\n⚠️ *Upcoming News:* " + ", ".join([f"{n['title']} ({n['minutes_away']}m)" for n in upcoming_news])

        return {
            'symbol': symbol,
            'direction': direction,
            'setup_quality': setup_quality,
            'entry_tf': "M5",
            'liquidity_event': f"{sweep_type} at {sweep_level:.5f}",
            'entry_zone': f"{m5_df.iloc[-1]['close']:.5f}",
            'entry_price': m5_df.iloc[-1]['close'],
            'sl': levels['sl'],
            'tp0': levels['tp0'],
            'tp1': levels['tp1'],
            'tp2': levels['tp2'],
            'layers': layers,
            'atr_status': atr_status,
            'session': session,
            'confidence': confidence,
            'news_warning': news_warning,
            'ai_logic': ai_result.get('institutional_logic', 'Institutional volume confirmed via liquidity sweep.'),
            'win_prob': win_prob,
            'confluence': confluence_text,
            'risk_details': risk_details,
            'asian_sweep': asian_sweep,
            'asian_quality': asian_quality,
            'adr_exhausted': adr_exhausted,
            'adr_usage': round((current_range / adr * 100), 1) if adr > 0 else 0,
            'at_value': at_value,
            'poc': poc,
            'ema_slope': ema_slope,
            'crt_phase': crt_validation.get('phase', 'ACC'),
            'h4_sweep': h4_sweep
        }
    
    return None

async def main():
    is_actions = os.getenv("GITHUB_ACTIONS") == "true"
    
    if is_actions:
        print("🤖 GITHUB ACTIONS DETECTED: Running Single-Shot Scan (V6.1)")
    else:
        print("🛡️ V7.2 QUANTUM SHIELD LIVE SCANNER STARTING...")
    
    print(f"Monitoring: {', '.join([s.split('=')[0].replace('^IXIC', 'NASDAQ') for s in SYMBOLS])}")
    
    telegram_service = TelegramService()
    ai_analyst = AIAnalyst()
    renderer = TVChartRenderer()
    journal = SignalJournal()
    
    # Startup Heartbeat
    if os.getenv("SEND_HEARTBEAT") == "true":
        await telegram_service.test_connection()
        
    last_processed_candle = {}
    
    while True:
        try:
            news_fetcher = NewsFetcher()
            news_events = news_fetcher.fetch_news()
            
            fetcher = DataFetcher()
            market_data = await fetcher.get_latest_data()
            
            if not market_data:
                if is_actions: break
                await asyncio.sleep(60)
                continue
            
            tasks = []
            for symbol, data in market_data.items():
                if symbol == 'DXY': continue
                
                # Deduplication (only for local continuous mode)
                if not is_actions:
                    latest_time = data['m5'].index[-1]
                    if last_processed_candle.get(symbol) == latest_time:
                        continue
                    last_processed_candle[symbol] = latest_time
                
                tasks.append(process_symbol(symbol, data, news_events, ai_analyst, market_data))
            
            if not tasks:
                if is_actions: break
                await asyncio.sleep(60)
                continue

            potential_signals = await asyncio.gather(*tasks)
            valid_signals = [s for s in potential_signals if s is not None]

            if valid_signals:
                # 11. Portfolio Correlation Filter
                filtered_signals = CorrelationAnalyzer.filter_signals(valid_signals)
                
                for signal in filtered_signals:
                    # Capture Chart
                    try:
                        photo = await renderer.render_chart(signal['symbol'], market_data[signal['symbol']])
                        message = telegram_service.format_signal(signal)
                        await telegram_service.send_chart(photo, message)
                    except Exception as e:
                        print(f"Renderer Error: {e}")
                        # Fallback to text signaling
                        message = telegram_service.format_signal(signal)
                        await telegram_service.send_signal(message)
                    
                    # Log to Journal
                    journal.log_signal(signal)
            
            if is_actions: 
                print("✅ GitHub Actions Scan Complete.")
                break
                
        except Exception as e:
            if is_actions: raise e
            print(f"Error in main loop: {e}")
            await asyncio.sleep(30)
            
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
