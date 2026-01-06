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
            up='#26a69a', down='#ef5350',
            edge='inherit', wick='inherit', volume='in', ohlc='inherit'
        )
        style = mpf.make_mpf_style(
            base_mpf_style='yahoo', marketcolors=mc, gridstyle='--', facecolor='white', gridcolor='#d1d5db'
        )
        
        # Buffer
        buf = io.BytesIO()
        
        # Title
        title = f"\n{symbol} - {direction} ({trade_details.get('setup_tf', 'M5')})"
        
        try:
            # Plot with returnfig=True to get access to axes
            fig, axlist = mpf.plot(
                plot_df,
                type='candle',
                style=style,
                addplot=apds,
                hlines=hlines,
                title=title,
                volume=False,
                figsize=(12, 8),
                tight_layout=True,
                returnfig=True
            )
            
            # Access the main ax (first one)
            ax = axlist[0]
            
            # Create Info Box Content
            ai_logic = trade_details.get('ai_logic', 'N/A')
            # Truncate logic if too long
            if len(ai_logic) > 60: ai_logic = ai_logic[:57] + "..."
            
            metrics_text = (
                f"AI Rationale: {ai_logic}\n"
                f"Confidence:   {trade_details.get('confidence', 0)}/10\n"
                f"ML Win Prob:  {trade_details.get('win_prob', 0)*100:.1f}%\n"
                f"EMA Slope:    {trade_details.get('ema_slope', 0):.3f}%\n"
                f"ADR Usage:    {trade_details.get('adr_usage', 0)}%"
            )
            
            # Add Text Box (AnchoredText)
            # We need matplotlib.offsetbox for this
            from matplotlib.offsetbox import AnchoredText
            at = AnchoredText(
                metrics_text,
                loc='upper left',
                prop=dict(size=9, family='monospace'),
                frameon=True,
            )
            at.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")
            at.patch.set_alpha(0.8)
            at.patch.set_facecolor('#f0f0f0') # Light gray background
            ax.add_artist(at)
            
            # Save the figure
            fig.savefig(buf, dpi=120, bbox_inches='tight', pad_inches=0.5)
            buf.seek(0)
            return buf
            
        except Exception as e:
            print(f"Error generating chart for {symbol}: {e}")
            return None
