import mplfinance as mpf
import pandas as pd
import io
from config.config import EMA_TREND, EMA_FAST, EMA_SLOW
from indicators.calculations import IndicatorCalculator

class ChartGenerator:
    @staticmethod
    def generate_chart(symbol: str, df: pd.DataFrame, trade_details: dict) -> io.BytesIO:
        """
        Generates a candlestick chart with indicators and trade levels.
        Returns the image as a BytesIO buffer.
        """
        # Calculate indicators if missing (Chart needs M5 indicators)
        df_chart = IndicatorCalculator.add_indicators(df.copy(), "m5")
        
        # Ensure we have enough data (last 100 bars)
        plot_df = df_chart.tail(100).copy()
        
        # Create plots for EMAs
        apds = [
            mpf.make_addplot(plot_df[f'ema_{EMA_FAST}'], color='blue', width=1.0),
            mpf.make_addplot(plot_df[f'ema_{EMA_SLOW}'], color='orange', width=1.0),
            mpf.make_addplot(plot_df[f'ema_{EMA_TREND}'], color='purple', width=1.5)
        ]
        
        # Determine colors based on direction
        direction = trade_details.get('direction', 'BUY')
        entry_color = 'green' if direction == 'BUY' else 'red'
        sl_color = 'red' if direction == 'BUY' else 'green' # SL is opposite logic? No, SL is always bad/loss, usually Red. TP is Green.
        # Let's use standard: Entry=Blue, SL=Red, TP=Green
        
        # Horizontal lines for levels
        hlines = dict(
            hlines=[
                trade_details.get('entry', 0), 
                trade_details.get('sl', 0), 
                trade_details.get('tp1', 0), 
                trade_details.get('tp2', 0)
            ],
            colors=['blue', 'red', 'green', 'green'],
            linestyle=['-', '--', '-.', ':'],
            linewidths=[1.5, 1.5, 1.0, 1.0]
        )
        
        # Custom "TradingView-like" Style
        mc = mpf.make_marketcolors(
            up='#26a69a', down='#ef5350', # TradingView standard Green/Red
            edge='inherit',
            wick='inherit',
            volume='in',
            ohlc='inherit'
        )
        
        style = mpf.make_mpf_style(
            base_mpf_style='yahoo', 
            marketcolors=mc, 
            gridstyle='--', 
            facecolor='white',
            gridcolor='#d1d5db'
        )
        
        # Buffer to save image
        buf = io.BytesIO()
        
        # Plot
        title = f"\n{symbol} - {direction} ({trade_details.get('setup_tf', 'M5')})"
        
        try:
            mpf.plot(
                plot_df,
                type='candle',
                style=style,
                addplot=apds,
                hlines=hlines,
                title=title,
                volume=False,
                savefig=dict(fname=buf, dpi=120, bbox_inches='tight', pad_inches=0.5),
                figsize=(12, 8),
                tight_layout=True
            )
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Error generating chart for {symbol}: {e}")
            return None
