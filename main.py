import asyncio
import logging
import joblib
import os
from config.config import SYMBOLS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from data.news_fetcher import NewsFetcher
from alerts.service import TelegramService
from ai.analyst import AIAnalyst
from filters.correlation import CorrelationAnalyzer
from tools.tv_renderer import TVChartRenderer
from audit.journal import SignalJournal
from audit.performance_analyzer import PerformanceAnalyzer
from strategies.smc_strategy import SMCStrategy
from strategies.breakout_strategy import BreakoutStrategy
from strategies.price_action_strategy import PriceActionStrategy
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

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def process_symbol(symbol: str, data: dict, news_events: list, ai_analyst: AIAnalyst, data_batch: dict, strategies: list) -> list:
    # 1. Add Indicators to all timeframes (Pre-processing for all strategies)
    h1_df = IndicatorCalculator.add_indicators(data['h1'], "h1")
    m15_df = IndicatorCalculator.add_indicators(data['m15'], "m15")
    m5_df = IndicatorCalculator.add_indicators(data['m5'], "m5")
    
    updated_data = {
        'h1': h1_df, 
        'm15': m15_df, 
        'm5': m5_df, 
        'h4': data.get('h4'),
        'd1': data.get('d1')
    }
    
    # V15.0 Performance: Parallelize strategy analysis per symbol
    tasks = [strategy.analyze(symbol, updated_data, news_events, data_batch) for strategy in strategies]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    signals = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Strategy {strategies[i].get_name()} Error on {symbol}: {result}")
            continue
        if result:
            # Apply Dynamic Strategy Multiplier
            multiplier = PerformanceAnalyzer.get_strategy_multiplier(strategies[i].get_id())
            result['confidence'] = round(result['confidence'] * multiplier, 1)
            result['pair'] = result.get('pair', symbol)
            signals.append(result)
            
    return signals

async def main():
    is_actions = os.getenv("GITHUB_ACTIONS") == "true"
    
    if is_actions:
        logger.info("🤖 GITHUB ACTIONS DETECTED: Running Single-Shot Scan (V6.1)")
    else:
        logger.info("🛡️ V7.2 QUANTUM SHIELD LIVE SCANNER STARTING...")
    
    logger.info(f"Monitoring: {', '.join([s.split('=')[0].replace('^IXIC', 'NASDAQ') for s in SYMBOLS])}")
    
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
            logger.info(f"Fetched Data Keys: {list(market_data.keys())}")
            
            if not market_data:
                if is_actions:
                    break
                await asyncio.sleep(60)
                continue
            
            tasks = []
            for symbol, data in market_data.items():
                if symbol in ['DXY', '^TNX']:
                    continue
                
                # Deduplication (only for local continuous mode)
                if not is_actions:
                    # Robust check for m5 availability
                    if 'm5' not in data:
                        logger.warning(f"Skipping {symbol}: Missing 'm5' data. Available: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                        continue
                        
                    latest_time = data['m5'].index[-1]
                    if last_processed_candle.get(symbol) == latest_time:
                        continue
                    last_processed_candle[symbol] = latest_time
                
                tasks.append(process_symbol(symbol, data, news_events, ai_analyst, market_data, strategies))
            
            if not tasks:
                if is_actions:
                    break
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
                        logger.error(f"Renderer Error: {e}")
                        # Fallback to text signaling
                        message = telegram_service.format_signal(signal)
                        await telegram_service.send_signal(message)
                    
                    # Log to Journal
                    journal.log_signal(signal)
            
            if is_actions: 
                logger.info("✅ GitHub Actions Scan Complete.")
                break
                
        except Exception as e:
            if is_actions:
                raise e
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(30)
            
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
