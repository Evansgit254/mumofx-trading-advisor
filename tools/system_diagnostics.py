import asyncio
import pandas as pd
from datetime import datetime, timezone
from data.fetcher import DataFetcher
from filters.session_filter import SessionFilter
from filters.news_filter import NewsFilter
from data.news_fetcher import NewsFetcher
from config.config import SYMBOLS

async def run_diagnostics():
    print("🏥 Starting System Diagnostics...")
    
    # 1. Check Time & Session
    now_utc = datetime.now(timezone.utc)
    print(f"\n🕒 Current Time (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if session is valid
    is_valid = SessionFilter.is_valid_session()
    session_name = SessionFilter.get_session_name()
    
    print(f"🌍 Detected Session: {session_name} (Active: {is_valid})")
    if not is_valid:
        print("⚠️ WARNING: No Active Session detected. System sleeps outside sessions.")
    
    # 2. Check Data Feed (EURUSD)
    print(f"\n📡 Testing Data Feed (EURUSD)...")
    df = DataFetcher.fetch_data("EURUSD=X", "5m")
    if df is None or df.empty:
        print("❌ CRITICAL: No Data received for EURUSD. API or Connection Issue.")
    else:
        last_time = df.index[-1]
        print(f"✅ Data Received. Latest Candle: {last_time}")
        time_diff = (now_utc - last_time).total_seconds() / 60
        if time_diff > 15:
            print(f"⚠️ WARNING: Data is stale! ({time_diff:.1f} mins old). Market might be closed or API delayed.")
        else:
            print("✅ Data is fresh.")
            
    # 3. Check News Filter
    print(f"\n📰 Checking high-impact news...")
    try:
        events = NewsFetcher.fetch_news()
        upcoming = NewsFilter.get_upcoming_events(events, "EURUSD=X")
        if upcoming:
            print(f"⚠️ WARNING: Trading possibly paused due to News: {[e['title'] for e in upcoming]}")
        else:
            print("✅ No immediate news blocking trades.")
    except Exception as e:
        print(f"⚠️ News Check Failed: {e}")
            
    print("\n🏁 Diagnostics Complete.")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
