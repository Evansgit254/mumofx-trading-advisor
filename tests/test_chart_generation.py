import pandas as pd
import mplfinance as mpf
from tools.charting import ChartGenerator
import os

def test_chart_generation():
    print("🎨 Testing Chart Generation...")
    
    # Create dummy M5 data
    dates = pd.date_range(start='2024-01-01', periods=200, freq='5min')
    df = pd.DataFrame({
        'open': [1.0500 + i*0.0001 for i in range(200)],
        'high': [1.0505 + i*0.0001 for i in range(200)],
        'low': [1.0495 + i*0.0001 for i in range(200)],
        'close': [1.0502 + i*0.0001 for i in range(200)],
        'volume': [1000 for _ in range(200)]
    }, index=dates)
    
    # Signal details
    signal = {
        'symbol': 'EURUSD',
        'direction': 'BUY',
        'setup_tf': 'M15',
        'entry': 1.0700,
        'sl': 1.0690,
        'tp1': 1.0720,
        'tp2': 1.0750
    }
    
    try:
        buf = ChartGenerator.generate_chart('EURUSD', df, signal)
        if buf:
            with open("test_chart.png", "wb") as f:
                f.write(buf.getvalue())
            print("✅ Chart generated successfully (saved to test_chart.png)")
        else:
            print("❌ Chart generation failed (returned None)")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_chart_generation()
