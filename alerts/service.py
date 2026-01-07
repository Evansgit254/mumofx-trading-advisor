import asyncio
import telegram
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

class TelegramService:
    def __init__(self):
        self.bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
        self.chat_id = TELEGRAM_CHAT_ID

    async def send_signal(self, message: str):
        """
        Sends a signal message to Telegram.
        """
        if not self.bot or not self.chat_id:
            print("[ALERTS] Telegram credentials missing. Check your .env or GitHub Secrets.")
            return

        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='Markdown')
        except Exception as e:
            print(f"[ALERTS] Error sending Telegram message: {e}")

    async def test_connection(self):
        """
        Sends a heartbeat message to verify the bot is alive and credentials are correct.
        """
        if not self.bot or not self.chat_id:
            print("[ALERTS] Connection Test Failed: Credentials missing.")
            return False
            
        try:
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text="🔔 *SMC BOT HEARTBEAT*: Connection Successful. Scan starting...", 
                parse_mode='Markdown'
            )
            print("[ALERTS] Connection Test: SUCCESS")
            return True
        except Exception as e:
            print(f"[ALERTS] Connection Test Failed: {e}")
            return False
    async def send_chart(self, photo, caption: str):
        """
        Sends a chart image with caption.
        """
        if not self.bot or not self.chat_id:
            print("Telegram credentials missing. Chart not sent.")
            return

        try:
            # Telegram requires file pointer to be at start
            photo.seek(0) 
            await self.bot.send_photo(chat_id=self.chat_id, photo=photo, caption=caption, parse_mode='Markdown')
        except Exception as e:
            print(f"Error sending Telegram chart: {e}")
    def format_signal(self, data: dict) -> str:
        """
        Formats signal data into the strict Telegram format.
        """
        header = "⚡ *SMC TOP-DOWN SETUP*"
        emoji = "⚡" # Default emoji
        if "GC=F" in data.get('symbol', ''):
            emoji = "🚀" if data['direction'] == "BUY" else "☄️"
        
        return f"""
{emoji} *NEW {data['setup_quality']} SETUP* {"💎 (LAYERING RECOMMENDED)" if data['setup_quality'] == "A+" else ""}
*Symbol:* #{data['symbol'].replace('=X', '').replace('_', '\\_')}
*Market Bias:* {data['direction']} (Institutional)
*TF:* {data['entry_tf']} | {data['session']} Session

🎯 *LIQUID LAYERING (Milking Zone):*
1. {data['layers'][0]['label']}: **{data['layers'][0]['lots']} lots** @ {data['layers'][0]['price']:.5f}
2. {data['layers'][1]['label']}: **{data['layers'][1]['lots']} lots** @ {data['layers'][1]['price']:.5f}
3. {data['layers'][2]['label']}: **{data['layers'][2]['lots']} lots** @ {data['layers'][2]['price']:.5f}
_Total Vol: {sum(l['lots'] for l in data['layers']):.2f}_

🛑 *Stop Loss:*
• {data['sl']:.5f} (below sweep)

*Liquidity Event:*
• {data['liquidity_event'].replace('_', '\\_')}

🧠 *AI Market Analysis:*
• {data['ai_logic']}
{data.get('confluence', '')}

*Entry Zone:*
• {data['entry_zone']}

🛡️ *Micro-Account Risk (V3.2):*
• Recommended Lots: `{data['risk_details']['lots']}`
• Risk Amount: `${data['risk_details']['risk_cash']}` ({data['risk_details']['risk_percent']}%)
• SL Distance: {data['risk_details']['pips']} pips
{data['risk_details']['warning']}

*Stop Loss:*
• {data['sl']:.5f} (below sweep)

*Take Profit:*
• TP0 (Partial + BE): {data['tp0']:.5f} (Close 50%)
• TP1: {data['tp1']:.5f}
• TP2: {data['tp2']:.5f}

🎯 *LIQUID REAPER MANAGEMENT:*
1. {"**🥇 GOLD SPECIALIST PARTIAL:** Close 50% @ TP0 + Move SL to BE" if "GC=F" in data.get('symbol', '') else "**At TP0:** Close 50% of position and MOVE SL TO BREAKEVEN."}
2. **At TP1:** Trail SL to TP0 (Lock in more profit).
3. **Final Target:** Let remaining 50% run to TP2.
4. **Safety Filter:** If price fails to hit TP0 but stalls for 30 mins, exit manually at BE.

*ATR:* {data['atr_status']}
*Session:* {data['session']}
📊 *Confidence:* {data['confidence']} / 10
🤖 *ML Win Probability:* {data['win_prob']*100:.1f}%

🎯 *Alpha Sniper (V6.0):*
• Session Sniper: {"✅ ASIAN SWEEP" if data.get('asian_sweep') else "Standard Liquidity"} {"(High Quality)" if data.get('asian_quality') else "(Low Range)"}
• Volume Sniper: {"⚠️ UNSAFE VALUE ZONE" if data.get('at_value') else "✅ EXTREME VALUE (INSTITUTIONAL)"} (POC: {data.get('poc', 0):.5f})
• Momentum Sniper: {"✅ IDEAL VELOCITY" if abs(data.get('ema_slope', 0)) < 0.05 else "⚠️ STEEP TREND (RISKY)"} (Slope: {data.get('ema_slope', 0):.4f}%)
• CRT Phase: {data.get('crt_phase', 'ACC')} {"📈 Expansion" if "DISTRIBUTION" in data.get('crt_phase', '') else "🔄 Range"}
• 4H Institution: {"✅ 4H SWEEP DETECTED" if data.get('h4_sweep') else "Standard Intraday"}
• ADR Usage: {data.get('adr_usage')}% {"⚠️ EXHAUSTED" if data.get('adr_exhausted') else "✅ HEALTHY"}

{data.get('news_warning', '')}

⏱ *Expected hold:* 5–20 minutes
⚠️ *Manual execution required*
"""
