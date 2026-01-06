import asyncio
import json
import os
import io
import pandas as pd
from playwright.async_api import async_playwright
from config.config import EMA_TREND, EMA_FAST, EMA_SLOW
from indicators.calculations import IndicatorCalculator

class TVChartRenderer:
    @staticmethod
    async def render_chart(symbol: str, df: pd.DataFrame, trade_details: dict) -> io.BytesIO:
        """
        Renders a TradingView chart using a headless browser.
        Returns bytes of the PNG screenshot.
        """
        # 1. Prepare Data
        # Ensure indicators exist
        df = IndicatorCalculator.add_indicators(df.copy(), "m5")
        
        # Format for Lightweight Charts (Time must be in seconds Unix timestamp)
        # Assuming df index is valid datetime
        
        candles = []
        ema20 = []
        ema50 = []
        ema100 = []
        
        for index, row in df.tail(150).iterrows():
            timestamp = int(index.timestamp())
            candles.append({
                'time': timestamp,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close']
            })
            
            # Handle NaN values for EMAs at start
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
                'ema20': ema20,
                'ema50': ema50,
                'ema100': ema100
            },
            'details': {
                'direction': trade_details.get('direction', 'BUY'),
                'timeframe': trade_details.get('setup_tf', 'M5'),
                'confidence': trade_details.get('confidence', 0),
                'win_prob': trade_details.get('win_prob', 0),
                'slope': trade_details.get('ema_slope', 0),
                'adr': trade_details.get('adr_usage', 0),
                'rationale': trade_details.get('ai_logic', 'Data-driven setup.'),
                'entry': trade_details.get('entry', 0),
                'sl': trade_details.get('sl', 0),
                'tp1': trade_details.get('tp1', 0)
            }
        }

        # 2. Launch Browser & Render
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 1200, 'height': 800})
            
            # Load the HTML template
            # We need an absolute path
            template_path = os.path.abspath("assets/tv_chart.html")
            await page.goto(f"file://{template_path}")
            
            # Inject Data and Render
            await page.evaluate(f"renderChart({json.dumps(chart_data)})")
            
            # Wait a moment for rendering/animations (though we turned seconds off)
            await asyncio.sleep(0.5)
            
            # Screenshot
            screenshot_bytes = await page.screenshot(type='png')
            await browser.close()
            
            return io.BytesIO(screenshot_bytes)
