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
        
        # Style
        style = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle=':', facecolor='white')
        
        # Buffer to save image
        buf = io.BytesIO()
        
        # Plot
        title = f"{symbol} - {direction} SETUP ({trade_details.get('setup_tf', '')})"
        
        try:
            mpf.plot(
                plot_df,
                type='candle',
                style=style,
                addplot=apds,
                hlines=hlines,
                title=title,
                volume=False,
                savefig=dict(fname=buf, dpi=100, bbox_inches='tight'),
                figsize=(10, 6)
            )
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Error generating chart for {symbol}: {e}")
            return None
