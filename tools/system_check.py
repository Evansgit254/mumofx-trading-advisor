import os
import sys
from dotenv import load_dotenv

def check_env():
    load_dotenv()
    print("📋 SMC SYSTEM HEALTH CHECK")
    print("-" * 30)
    
    secrets = {
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY")
    }
    
    all_ok = True
    for name, val in secrets.items():
        status = "✅ CONFIGURED" if val else "❌ MISSING"
        if not val: all_ok = False
        # Obfuscate token for privacy
        preview = f"({val[:5]}...{val[-5:]})" if val and len(val) > 10 else ""
        print(f"{name:20}: {status} {preview}")
        
    print("-" * 30)
    
    # Check dependencies
    try:
        import pandas
        import pandas_ta
        import telegram
        import sklearn
        print("📦 Dependencies: ✅ ALL LOADED")
    except ImportError as e:
        print(f"📦 Dependencies: ❌ {e}")
        all_ok = False
        
    if all_ok:
        print("\n🚀 SYSTEM READY FOR PRODUCTION!")
    else:
        print("\n⚠️ SYSTEM NOT READY. Please check the missing items above.")

if __name__ == "__main__":
    check_env()
