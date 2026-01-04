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
from strategy.scoring import ScoringEngine
from alerts.service import TelegramService

async def process_symbol(symbol: str, data: dict, telegram_service: TelegramService, news_events: list):
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
        return

    # 3. Detect Liquidity Sweep (M15 preferred for intraday)
    sweep = LiquidityDetector.detect_sweep(m15_df, bias, timeframe="m15")
    if not sweep:
        # Fallback to M5 sweep if M15 is quiet
        sweep = LiquidityDetector.detect_sweep(m5_df, bias, timeframe="m5")
        if not sweep:
            return

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
        return

    # 7. Scoring
    score_details = {
        'bias_strength': True,
        'sweep_type': sweep['type'],
        'displaced': displaced,
        'pullback': entry is not None,
        'session': session,
        'volatile': volatile
    }
    confidence = ScoringEngine.calculate_score(score_details)

    # 8. Alert
    if confidence >= MIN_CONFIDENCE_SCORE:
        atr = m5_df.iloc[-1]['atr']
        levels = EntryLogic.calculate_levels(m5_df, direction, sweep['level'], atr)
        
        upcoming_news = NewsFilter.get_upcoming_events(news_events, symbol)
        news_warning = ""
        if upcoming_news:
            news_warning = "⚠️ *NEWS WARNING*:\n"
            for n in upcoming_news:
                bias_str = f" [{n['bias']}]" if n['bias'] != "NEUTRAL" else ""
                news_warning += f"• {n['impact']} Impact: {n['title']}{bias_str} ({n['minutes_away']}m)\n"

        signal_data = {
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
            'news_warning': news_warning
        }
        
        message = telegram_service.format_signal(signal_data)
        await telegram_service.send_signal(message)

async def main():
    print(f"🚀 Starting SMC Top-Down Intraday Engine... {datetime.now()}")
    
    # 1. Fetch News
    news_events = NewsFetcher.fetch_news()
    
    # 2. Fetch Market Data
    fetcher = DataFetcher()
    market_data = fetcher.get_latest_data()
    
    telegram_service = TelegramService()
    
    tasks = []
    for symbol, data in market_data.items():
        tasks.append(process_symbol(symbol, data, telegram_service, news_events))
    
    await asyncio.gather(*tasks)
    print("Execution completed.")

if __name__ == "__main__":
    asyncio.run(main())
