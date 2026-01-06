import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

class TradingDashboard:
    def __init__(self, db_path="database/signals.db"):
        self.db_path = db_path

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def run(self):
        self.clear_screen()
        print("="*60)
        print("🚀 LIQUID REAPER V11.0 - PERFORMANCE DASHBOARD")
        print("="*60)
        
        if not os.path.exists(self.db_path):
            print("❌ No signals database found. Run the scanner first!")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query("SELECT * FROM signals", conn)
            conn.close()
            
            if df.empty:
                print("📭 Journal is empty. Waiting for institutional setups...")
                return

            # Convert types
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 1. Global Stats
            total_signals = len(df)
            resolved = df[df['status'] != 'PENDING']
            wins = len(resolved[resolved['status'].isin(['WIN', 'WIN_PARTIAL'])])
            win_rate = (wins / len(resolved) * 100) if not resolved.empty else 0
            total_pips = resolved['result_pips'].sum()
            
            print(f"🌍 GLOBAL PERFORMANCE")
            print(f"• Total Signals Generated: {total_signals}")
            print(f"• Resolved Signals:         {len(resolved)}")
            print(f"• Win Rate:                {win_rate:.1f}%")
            print(f"• Total Pips Harvested:    {total_pips:+.1f} pips")
            print("-" * 60)

            # 2. Daily Pulse
            today = datetime.now().date()
            today_df = resolved[resolved['timestamp'].dt.date == today]
            today_pips = today_df['result_pips'].sum()
            print(f"🕒 TODAY'S PULSE ({today})")
            print(f"• Trades Today: {len(today_df)}")
            print(f"• Pips Today:   {today_pips:+.1f} pips")
            print("-" * 60)

            # 3. Symbol Leaderboard
            if not resolved.empty:
                print(f"📊 SYMBOL LEADERBOARD (Top Pips)")
                symbol_stats = resolved.groupby('symbol')['result_pips'].sum().sort_values(ascending=False)
                for sym, pips in symbol_stats.head(5).items():
                    print(f"• {sym:10} | {pips:+.1f} pips")
                print("-" * 60)

            # 4. Recent Trade Feed
            print(f"📜 RECENT TRADE FEED (Last 10)")
            feed = df.sort_values(by='timestamp', ascending=False).head(10)
            print(f"{'Time':<10} | {'Pair':<10} | {'Result':<12} | {'Pips':<8}")
            for _, row in feed.iterrows():
                time_str = row['timestamp'].strftime("%H:%M")
                pips_str = f"{row['result_pips']:+.1f}" if row['status'] != 'PENDING' else "---"
                print(f"{time_str:<10} | {row['symbol']:<10} | {row['status']:<12} | {pips_str:<8}")

        except Exception as e:
            print(f"❌ Dashboard Error: {e}")

        print("="*60)
        print(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    dashboard = TradingDashboard()
    dashboard.run()
