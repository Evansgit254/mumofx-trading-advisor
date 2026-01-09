import asyncio
import pandas as pd
from datetime import datetime
from config.config import (
    SYMBOLS, 
    MIN_CONFIDENCE_SCORE, 
    GOLD_CONFIDENCE_THRESHOLD,
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
from audit.performance_analyzer import PerformanceAnalyzer
from strategies.smc_strategy import SMCStrategy
from strategies.breakout_strategy import BreakoutStrategy
from strategies.price_action_strategy import PriceActionStrategy

import joblib
import os

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def process_symbol(symbol: str, data: dict, news_events: list, ai_analyst: AIAnalyst, data_batch: dict, strategies: list) -> list:
    # 1. Add Indicators to all timeframes (Pre-processing for all strategies)
    h1_df = IndicatorCalculator.add_indicators(data['h1'], "h1")
    m15_df = IndicatorCalculator.add_indicators(data['m15'], "m15")
    m5_df = IndicatorCalculator.add_indicators(data['m5'], "m5")
    
    updated_data = {'h1': h1_df, 'm15': m15_df, 'm5': m5_df, 'h4': data['h4']}
    
    signals = []
    for strategy in strategies:
        try:
            signal = await strategy.analyze(symbol, updated_data, news_events, data_batch)
            if signal:
                # Apply Dynamic Strategy Multiplier
                multiplier = PerformanceAnalyzer.get_strategy_multiplier(strategy.get_id())
                signal['confidence'] = round(signal['confidence'] * multiplier, 1)
                signals.append(signal)
        except Exception as e:
            print(f"Strategy {strategy.get_name()} Error on {symbol}: {e}")
            
    return signals

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
        
    # Initialize Strategies
    strategies = [SMCStrategy(), BreakoutStrategy(), PriceActionStrategy()]
    analyzer = PerformanceAnalyzer()
    analyzer.calculate_weights() # Initial calculation
    
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
                
                tasks.append(process_symbol(symbol, data, news_events, ai_analyst, market_data, strategies))
            
            if not tasks:
                if is_actions: break
                await asyncio.sleep(60)
                continue

            results = await asyncio.gather(*tasks)
            # results is a list of lists (signals from each strategy)
            valid_signals = [s for sublist in results for s in sublist if s is not None]

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
