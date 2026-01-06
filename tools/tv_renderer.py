import asyncio
import json
import os
import io
import pandas as pd
from playwright.async_api import async_playwright
from config.config import EMA_TREND, EMA_FAST, EMA_SLOW
from indicators.calculations import IndicatorCalculator

class TVChartRenderer:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.template_path = os.path.abspath("assets/tv_chart.html")

    async def start(self):
        """Initializes the browser session."""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch()

    async def stop(self):
        """Closes the browser session."""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            self.browser = None
            self.playwright = None

    async def render_chart(self, symbol: str, df: pd.DataFrame, trade_details: dict) -> io.BytesIO:
        """
        Renders a TradingView chart. Uses an existing browser if start() was called.
        """
        # Ensure browser is running
        internal_session = False
        if not self.browser:
            await self.start()
            internal_session = True

        try:
            # 1. Prepare Data
            df = IndicatorCalculator.add_indicators(df.copy(), "m5")
            
            candles = []
            ema20 = []
            ema50 = []
            ema100 = []
            
            for index, row in df.tail(150).iterrows():
                timestamp = int(index.timestamp())
                candles.append({
                    'time': timestamp,
                    'open': row['open'], 'high': row['high'],
                    'low': row['low'], 'close': row['close']
                })
                
                if not pd.isna(row[f'ema_{EMA_FAST}']):
                    ema20.append({'time': timestamp, 'value': row[f'ema_{EMA_FAST}']})
                if not pd.isna(row[f'ema_{EMA_SLOW}']):
                    ema50.append({'time': timestamp, 'value': row[f'ema_{EMA_SLOW}']})
                if not pd.isna(row[f'ema_{EMA_TREND}']):
                    ema100.append({'time': timestamp, 'value': row[f'ema_{EMA_TREND}']})

            chart_data = {
                'symbol': symbol,
                'candles': candles,
                'indicators': {
                    'ema20': ema20, 'ema50': ema50, 'ema100': ema100
                },
                'details': {
                    'direction': trade_details.get('direction', 'BUY'),
                    'timeframe': trade_details.get('setup_tf', 'M5'),
                    'confidence': trade_details.get('confidence', 0),
                    'win_prob': trade_details.get('win_prob', 0),
                    'slope': trade_details.get('ema_slope', 0),
                    'adr': trade_details.get('adr_usage', 0),
                    'rationale': trade_details.get('ai_logic', 'Data-driven setup.'),
                    'entry': trade_details.get('entry_price', 0),
                    'sl': trade_details.get('sl', 0),
                    'tp0': trade_details.get('tp0', 0),
                    'tp1': trade_details.get('tp1', 0),
                    'tp2': trade_details.get('tp2', 0)
                }
            }

            # 2. Render in Page
            page = await self.browser.new_page(viewport={'width': 1200, 'height': 800})
            await page.goto(f"file://{self.template_path}")
            
            # Inject Data and Render
            await page.evaluate(f"renderChart({json.dumps(chart_data)})")
            
            # Wait a moment for rendering
            await asyncio.sleep(0.5)
            
            # Screenshot
            screenshot_bytes = await page.screenshot(type='png')
            await page.close()
            
            return io.BytesIO(screenshot_bytes)

        finally:
            if internal_session:
                await self.stop()
