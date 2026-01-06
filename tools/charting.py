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
            up='#00897b', down='#e53935', # Deep Teal and Soft Red (Pro Colors)
            edge='inherit', wick='inherit', volume='in', ohlc='inherit'
        )
        style = mpf.make_mpf_style(
            base_mpf_style='yahoo', 
            marketcolors=mc, 
            gridstyle='-', 
            facecolor='white', 
            gridcolor='#f0f0f0' # Very faint grid
        )
        
        # Buffer
        buf = io.BytesIO()
        
        # Cleaner Title
        title_text = f"{symbol}  {trade_details.get('setup_tf', 'M5')}  {direction}"
        
        try:
            # Plot with returnfig=True
            fig, axlist = mpf.plot(
                plot_df,
                type='candle',
                style=style,
                addplot=apds,
                hlines=hlines,
                title=dict(title=title_text, size=14, weight='bold'),
                volume=False,
                figsize=(12, 7), # Slightly wider aspect ratio
                tight_layout=True,
                returnfig=True,
                scale_width_adjustment=dict(candle=1.2) # Thicker candles
            )
            
            # Access the main ax
            ax = axlist[0]
            
            # Clean Metrics Text
            ai_logic = trade_details.get('ai_logic', 'N/A')
            if len(ai_logic) > 70: ai_logic = ai_logic[:67] + "..."
            
            # Formatted for alignment using monospaced numbers but sans-serif label if possible
            # or just clean spacing
            conf = trade_details.get('confidence', 0)
            prob = trade_details.get('win_prob', 0)*100
            slope = trade_details.get('ema_slope', 0)
            adr = trade_details.get('adr_usage', 0)
            
            metrics_text = (
                f"STRATEGY INSIGHTS\n"
                f"────────────────────────\n"
                f"Rationale: {ai_logic}\n"
                f"Score:     {conf}/10\n"
                f"Win Prob:  {prob:.1f}%\n"
                f"Veloctiy:  {slope:.3f}%\n"
                f"ADR Used:  {adr}%"
            )
            
            # Add Text Box (AnchoredText)
            from matplotlib.offsetbox import AnchoredText
            at = AnchoredText(
                metrics_text,
                loc='upper left',
                prop=dict(size=9, family='sans-serif', weight='normal'),
                frameon=True,
            )
            at.patch.set_boxstyle("square,pad=0.5")
            at.patch.set_linewidth(0.5)
            at.patch.set_edgecolor('#d1d5db')
            at.patch.set_alpha(0.9)
            at.patch.set_facecolor('white')
            ax.add_artist(at)
            
            # Save
            fig.savefig(buf, dpi=150, bbox_inches='tight', pad_inches=0.3) # Higher DPI
            buf.seek(0)
            return buf

            
        except Exception as e:
            print(f"Error generating chart for {symbol}: {e}")
            return None
