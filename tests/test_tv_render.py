import asyncio
import pandas as pd
from tools.tv_renderer import TVChartRenderer
import os

async def test_tv_render():
    print("🎥 Testing Headless TradingView Renderer...")
    
    # Create dummy M5 data
    dates = pd.date_range(start='2024-01-01', periods=200, freq='5min')
    df = pd.DataFrame({
        'open': [1.0500 + i*0.0001 for i in range(200)],
        'high': [1.0505 + i*0.0001 for i in range(200)],
        'low': [1.0495 + i*0.0001 for i in range(200)],
        'close': [1.0502 + i*0.0001 for i in range(200)],
        'volume': [1000 for _ in range(200)]
    }, index=dates)
    
    # Signal details with VERY distinct levels to avoid overlap
    signal = {
        'symbol': 'EURUSD',
        'direction': 'BUY',
        'setup_tf': 'M15',
        'confidence': 9.5,
        'win_prob': 0.92,
        'ema_slope': 0.12,
        'adr_usage': 45,
        'ai_logic': 'Institutional buying detected (SMC). Price has swept lower liquidity and is now reversing with momentum.',
        'entry_price': 1.0700,
        'sl': 1.0650, # 50 pips away
        'tp1': 1.0800, # 100 pips away (2:1 RR)
        'tp2': 1.0850
    }
    
    print(f"DEBUG: Entry={signal['entry_price']}, SL={signal['sl']}, TP1={signal['tp1']}, TP2={signal['tp2']}")
    
    try:
        renderer = TVChartRenderer()
        await renderer.start()
        buf = await renderer.render_chart('EURUSD', df, signal)
        await renderer.stop()
        
        if buf:
            with open("tv_chart_final.png", "wb") as f:
                f.write(buf.getvalue())
            print("✅ TV Chart generated successfully (saved to tv_chart_final.png)")
        else:
            print("❌ TV Chart generation failed (returned None)")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tv_render())
