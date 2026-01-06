import asyncio
import os
from dotenv import load_dotenv
from alerts.service import TelegramService

# Load credentials
load_dotenv()

async def test_manual_signal():
    print("🛰️ Initiating Manual Signal Test...")
    service = TelegramService()
    
    mock_data = {
        'pair': 'EURUSD (TEST)',
        'direction': 'BUY',
        'h1_trend': 'BULLISH',
        'setup_tf': 'M15',
        'entry_tf': 'M5',
        'liquidity_event': 'Manual Connectivity Test',
        'ai_logic': 'Manual bypass for connectivity verification.',
        'entry_zone': '1.0500',
        'sl': 1.0480,
        'tp0': 1.0510,
        'tp1': 1.0520,
        'tp2': 1.0550,
        'setup_quality': 'A+ PREMIER',
        'layers': [
            {'label': 'Aggressive Layer', 'price': 1.0500, 'lots': 0.01},
            {'label': 'Optimal Retest', 'price': 1.0495, 'lots': 0.01},
            {'label': 'Safety Layer', 'price': 1.0490, 'lots': 0.01}
        ],
        'atr_status': 'Normal',
        'session': 'TEST',
        'confidence': 10.0,
        'win_prob': 0.99,
        'symbol': 'EURUSD=X',
        'confluence': '✅ Manual System Check',
        'asian_sweep': True,
        'asian_quality': True,
        'at_value': True,
        'poc': 1.0505,
        'adr_exhausted': False,
        'adr_usage': 85.0,
        'risk_details': {
            'lots': 0.01,
            'risk_cash': 2.0,
            'risk_percent': 4.0,
            'pips': 20.0,
            'warning': ''
        }
    }
    
    message = service.format_signal(mock_data)
    print("📝 Formatted Message:")
    print(message)
    
    print("\n📤 Sending to Telegram...")
    # Only send if explicitly requested via environment variable
    if os.getenv("SEND_TEST_SIGNAL") == "true":
        await service.send_signal(message)
        print("✅ Test signal sent to Telegram!")
    else:
        print("⏭️ Skipping Telegram dispatch (SEND_TEST_SIGNAL != true).")
    
    print("✅ Test execution complete.")

if __name__ == "__main__":
    asyncio.run(test_manual_signal())
