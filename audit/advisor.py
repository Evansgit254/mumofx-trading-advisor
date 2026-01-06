import sqlite3
import pandas as pd
import asyncio
from alerts.service import TelegramService

class StrategyAdvisor:
    def __init__(self, db_path="database/signals.db"):
        self.db_path = db_path
        self.telegram = TelegramService()

    async def generate_weekly_report(self):
        print("🧠 Analyzing Trade Patterns...")
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query("SELECT * FROM signals WHERE status != 'PENDING'", conn)
            if df.empty:
                print("⚠️ Not enough data for advisor yet.")
                return

            # Basic Analytics
            total_trades = len(df)
            wins = len(df[df['status'].isin(['WIN', 'WIN_PARTIAL'])])
            win_rate = (wins / total_trades) * 100
            
            # Session Analysis
            session_stats = df.groupby('session')['status'].apply(lambda x: (x.isin(['WIN', 'WIN_PARTIAL']).sum() / len(x)) * 100)
            
            # Quality Analysis
            # Note: We need to map confidence back to grades A+, A, B
            df['grade'] = ['A+ PREMIER' if c >= 9.5 else 'A SOLID' if c >= 8.5 else 'B STANDARD' for c in df['confidence']]
            grade_stats = df.groupby('grade')['status'].apply(lambda x: (x.isin(['WIN', 'WIN_PARTIAL']).sum() / len(x)) * 100)

            # Suggestions logic
            suggestions = []
            if win_rate < 60:
                suggestions.append("⚠️ Overall Win Rate is below 60%. Suggestion: **Raise MIN_CONFIDENCE_SCORE to 9.0**.")
            
            worst_session = session_stats.idxmin()
            if session_stats.min() < 50:
                suggestions.append(f"❌ Weak Performance in **{worst_session}** session ({session_stats.min():.1f}% WR). Suggestion: **Avoid trading this session**.")
            
            if grade_stats.get('B STANDARD', 100) < 40:
                suggestions.append("📉 B Standard setups are underperforming. Suggestion: **Raise minimum quality to A SOLID**.")

            # Format Telegram Message
            report = (
                "🤖 **V10.0 AUTONOMOUS STRATEGY ADVISOR**\n\n"
                f"📊 **Performance Summary (Last {len(df)} trades):**\n"
                f"• Win Rate: {win_rate:.1f}%\n"
                f"• Best Session: {session_stats.idxmax()} ({session_stats.max():.1f}%)\n"
                f"• A+ Success Rate: {grade_stats.get('A+ PREMIER', 0):.1f}%\n\n"
                "💡 **Optimization Suggestions:**\n"
            )
            
            if suggestions:
                report += "\n".join(suggestions)
            else:
                report += "✅ Strategy is highly optimized. No changes recommended."

            await self.telegram.send_signal(report)
            print("📬 Advisor report sent to Telegram.")
            
        except Exception as e:
            print(f"❌ Advisor Error: {e}")

if __name__ == "__main__":
    advisor = StrategyAdvisor()
    asyncio.run(advisor.generate_weekly_report())
