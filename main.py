import asyncio
import pandas as pd
from datetime import datetime
from config.config import SYMBOLS, MIN_CONFIDENCE_SCORE
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
from telegram.service import TelegramService

async def process_symbol(symbol: str, data: dict, telegram_service: TelegramService, news_events: list):
    m5_df = data['m5']
    m1_df = data['m1']

    # 1. Add Indicators
    m5_df = IndicatorCalculator.add_indicators(m5_df, "m5")
    m1_df = IndicatorCalculator.add_indicators(m1_df, "m1")

    # 2. Get Bias (M5)
    bias = BiasAnalyzer.get_bias(m5_df)
    if bias == "NEUTRAL":
        return

    # 3. Detect Liquidity Sweep (M1)
    sweep = LiquidityDetector.detect_sweep(m1_df, bias)
    if not sweep:
        return

    # 4. Displacement Confirmation
    direction = "BUY" if bias == "BULLISH" else "SELL"
    displaced = DisplacementAnalyzer.is_displaced(m1_df, direction)
    
    # 5. Entry Logic (Pullback/RSI)
    entry = EntryLogic.check_pullback(m1_df, direction)
    
    # 6. Filters
    session = SessionFilter.get_session_name()
    volatile = VolatilityFilter.is_volatile(m1_df)
    atr_status = VolatilityFilter.get_atr_status(m1_df)
    
    # News Filter
    upcoming_news = NewsFilter.get_upcoming_events(news_events, symbol)
    is_news_safe = NewsFilter.is_news_safe(news_events, symbol)
    
    if not is_news_safe:
        print(f"Skipping {symbol} due to high impact news.")
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

    # 8. Alert if Score ≥ Threshold
    if confidence >= MIN_CONFIDENCE_SCORE:
        # Calculate SL/TP based on Entry price if available, else current close
        atr = m1_df.iloc[-1]['atr']
        levels = EntryLogic.calculate_levels(m1_df, direction, sweep['level'], atr)
        
        # News warning string
        news_warning = ""
        if upcoming_news:
            news_warning = "⚠️ *NEWS WARNING*:\n"
            for n in upcoming_news:
                bias_str = f" [{n['bias']}]" if n['bias'] != "NEUTRAL" else ""
                news_warning += f"• {n['impact']} Impact: {n['title']}{bias_str} ({n['minutes_away']}m)\n"

        signal_data = {
            'pair': symbol.replace('=X', ''),
            'direction': direction,
            'liquidity_event': sweep['description'],
            'entry_zone': f"{m1_df.iloc[-1]['close']:.5f} - {m1_df.iloc[-1]['close'] + (0.0001 if direction == 'BUY' else -0.0001):.5f}",
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
    print(f"Starting SMC Scalp Signal Engine... {datetime.now()}")
    
    # Validate Session
    if not SessionFilter.is_valid_session():
        print("Outside trading sessions. Skipping execution.")
        # return # Uncomment for production

    fetcher = DataFetcher()
    telegram_service = TelegramService()
    
    # Fetch Data
    market_data = fetcher.get_latest_data()
    
    # Fetch News
    news_events = NewsFetcher.fetch_news()
    
    tasks = []
    for symbol, data in market_data.items():
        tasks.append(process_symbol(symbol, data, telegram_service, news_events))
    
    await asyncio.gather(*tasks)
    print("Execution completed.")

if __name__ == "__main__":
    asyncio.run(main())
