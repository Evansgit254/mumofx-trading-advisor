import asyncio
import pandas as pd
from datetime import datetime
from config.config import SYMBOLS, MIN_CONFIDENCE_SCORE, NARRATIVE_TF, STRUCTURE_TF, ENTRY_TF
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from filters.session_filter import SessionFilter
from filters.volatility_filter import VolatilityFilter
from filters.news_filter import NewsFilter
from data.news_fetcher import NewsFetcher
from alerts.service import TelegramService
from ai.analyst import AIAnalyst
from filters.correlation import CorrelationAnalyzer
from filters.risk_manager import RiskManager
from config.config import SYMBOLS, MIN_CONFIDENCE_SCORE, NARRATIVE_TF, STRUCTURE_TF, ENTRY_TF, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS
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

    # 1. Add Indicators to all timeframes
    h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
    m15_df = IndicatorCalculator.add_indicators(m15_df, "m15")
    m5_df = IndicatorCalculator.add_indicators(m5_df, "m5")

    # 2. Top-Down Bias Analysis
    bias = BiasAnalyzer.get_bias(h1_df, m15_df)
    h1_trend = BiasAnalyzer.get_h1_trend(h1_df)
    
    if bias == "NEUTRAL":
        return None

    # 3. Detect Liquidity Sweep (M15 preferred for intraday)
    sweep = LiquidityDetector.detect_sweep(m15_df, bias, timeframe="m15")
    if not sweep:
        # Fallback to M5 sweep if M15 is quiet
        sweep = LiquidityDetector.detect_sweep(m5_df, bias, timeframe="m5")
        if not sweep:
            return None

    # 4. Displacement Confirmation (on Entry TF)
    direction = "BUY" if bias == "BULLISH" else "SELL"
    displaced = DisplacementAnalyzer.is_displaced(m5_df, direction)
    
    # 5. Entry Logic (Pullback on M5)
    entry = EntryLogic.check_pullback(m5_df, direction)
    
    # 6. Filters
    session = SessionFilter.get_session_name()
    volatile = VolatilityFilter.is_volatile(m5_df)
    atr_status = VolatilityFilter.get_atr_status(m5_df)
    is_news_safe = NewsFilter.is_news_safe(news_events, symbol)
    
    if not is_news_safe:
        print(f"Skipping {symbol} due to news.")
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
        if pips >= ASIAN_RANGE_MIN_PIPS:
            asian_quality = True
            
        if direction == "BUY" and m5_df.iloc[-1]['low'] < asian_range['low']:
            asian_sweep = True
        elif direction == "SELL" and m5_df.iloc[-1]['high'] > asian_range['high']:
            asian_sweep = True

    # 8. V5.0 Hyper-Quant: Volume Profile (POC)
    poc = IndicatorCalculator.calculate_poc(m5_df)
    atr = m5_df.iloc[-1]['atr']
    at_value = abs(m5_df.iloc[-1]['close'] - poc) <= (0.5 * atr) # Within 0.5 ATR of Value

    # 9. Scoring
    score_details = {
        'h1_aligned': h1_trend == direction.replace('BUY', 'BULLISH').replace('SELL', 'BEARISH'),
        'sweep_type': sweep['type'],
        'displaced': displaced,
        'pullback': entry is not None,
        'session': session,
        'volatile': volatile,
        'asian_sweep': asian_sweep,
        'asian_quality': asian_quality,
        'adr_exhausted': adr_exhausted,
        'at_value': at_value
    }
    confidence = ScoringEngine.calculate_score(score_details)

    # 8. AI Market Intelligence (Confirmation)
    ai_result = {"valid": True, "institutional_logic": "Standard liquidity alignment."}
    
    # Gold Specialist: Lower AI trigger to 8.5 for GC=F
    ai_threshold = 8.2 if "GC=F" in symbol else 8.5
    
    if confidence >= ai_threshold:
        ai_result = await ai_analyst.validate_signal({
            'pair': symbol,
            'direction': direction,
            'h1_trend': h1_trend,
            'setup_tf': sweep['type'],
            'liquidity_event': sweep['description'],
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
        dxy_trend = BiasAnalyzer.get_h1_trend(dxy_df)
        dxy_bias = "BULLISH" if dxy_trend == "BULLISH" else "BEARISH"
        
        # Gold and DXY are INVERSELY correlated
        if direction == "BUY" and dxy_bias == "BEARISH":
            confluence_text = "📊 *DXY Confluence:* ✅ Inverse Dollar weakness detected."
        elif direction == "SELL" and dxy_bias == "BULLISH":
            confluence_text = "📊 *DXY Confluence:* ✅ Inverse Dollar strength detected."
        else:
            confluence_text = "📊 *DXY Confluence:* ⚠️ Divergence from Dollar trend."

    # 11. Alert
    if confidence >= MIN_CONFIDENCE_SCORE:
        atr = m5_df.iloc[-1]['atr']
        levels = EntryLogic.calculate_levels(m5_df, direction, sweep['level'], atr)
        
        # V3.2: Risk Management for $50 Account
        risk_details = RiskManager.calculate_lot_size(symbol, m5_df.iloc[-1]['close'], levels['sl'])

        upcoming_news = NewsFilter.get_upcoming_events(news_events, symbol)
        news_warning = ""
        if upcoming_news:
            news_warning = "⚠️ *NEWS WARNING*:\n"
            for n in upcoming_news:
                bias_str = f" [{n['bias']}]" if n['bias'] != "NEUTRAL" else ""
                news_warning += f"• {n['impact']} Impact: {n['title']}{bias_str} ({n['minutes_away']}m)\n"

        return {
            'pair': symbol.replace('=X', ''),
            'direction': direction,
            'h1_trend': h1_trend,
            'setup_tf': sweep['type'].split('_')[0],
            'entry_tf': 'M5',
            'liquidity_event': sweep['description'],
            'entry_zone': f"{m5_df.iloc[-1]['close']:.5f} - {m5_df.iloc[-1]['close'] + (0.0001 if direction == 'BUY' else -0.0001):.5f}",
            'sl': levels['sl'],
            'tp1': levels['tp1'],
            'tp2': levels['tp2'],
            'atr_status': atr_status,
            'session': session,
            'confidence': confidence,
            'news_warning': news_warning,
            'ai_logic': ai_result.get('institutional_logic', 'Institutional volume confirmed via liquidity sweep.'),
            'win_prob': win_prob,
            'symbol': symbol,
            'confluence': confluence_text,
            'risk_details': risk_details,
            'asian_sweep': asian_sweep,
            'asian_quality': asian_quality,
            'adr_exhausted': adr_exhausted,
            'adr_usage': round((current_range / adr * 100), 1) if adr > 0 else 0,
            'at_value': at_value,
            'poc': poc
        }
    
    return None

async def main():
    print(f"🚀 Starting SMC Top-Down Intraday Engine... {datetime.now()}")
    
    # 1. Fetch News
    news_events = NewsFetcher.fetch_news()
    
    # 2. Fetch Market Data
    fetcher = DataFetcher()
    market_data = fetcher.get_latest_data()
    
    telegram_service = TelegramService()
    ai_analyst = AIAnalyst()
    
    tasks = []
    for symbol, data in market_data.items():
        if symbol == 'DXY': continue
        tasks.append(process_symbol(symbol, data, news_events, ai_analyst, market_data))
    
    potential_signals = await asyncio.gather(*tasks)
    valid_signals = [s for s in potential_signals if s is not None]
    
    # 3. Correlation Filter (V3.0)
    filtered_signals = CorrelationAnalyzer.filter_signals(valid_signals)
    theme_header = CorrelationAnalyzer.group_by_theme(filtered_signals)
    
    if theme_header:
        await telegram_service.send_signal(theme_header)
        
    for signal in filtered_signals:
        message = telegram_service.format_signal(signal)
        await telegram_service.send_signal(message)
        
    print(f"Execution completed. Found {len(filtered_signals)} aligned signals.")

if __name__ == "__main__":
    asyncio.run(main())
