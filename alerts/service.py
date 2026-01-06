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
            print("Telegram credentials missing. Signal:")
            print(message)
            return

        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='Markdown')
        except Exception as e:
            print(f"Error sending Telegram message: {e}")

    def format_signal(self, data: dict) -> str:
        """
        Formats signal data into the strict Telegram format.
        """
        header = "⚡ *SMC TOP-DOWN SETUP*"
        if "GC=F" in data.get('symbol', ''):
            header = "🏆 *GOLD SNIPER ELITE SETUP* 🥇"

        return f"""
{header}

*Pair:* {data['pair']}
*Direction:* {data['direction']}
*Style:* Intraday (SMC)
*Narrative (1H):* {data['h1_trend']}
*Setup TF:* {data['setup_tf']}
*Entry TF:* {data['entry_tf']}

*Liquidity Event:*
• {data['liquidity_event']}

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
• TP1: {data['tp1']:.5f}
• TP2: {data['tp2']:.5f}

🛡️ *PROFIT GUARD:* Move SL to Breakeven at TP1.

*ATR:* {data['atr_status']}
*Session:* {data['session']}
📊 *Confidence:* {data['confidence']} / 10
🤖 *ML Win Probability:* {data['win_prob']*100:.1f}%

🎯 *Alpha Sniper (V6.0):*
• Session Sniper: {"✅ ASIAN SWEEP" if data.get('asian_sweep') else "Standard Liquidity"} {"(High Quality)" if data.get('asian_quality') else "(Low Range)"}
• Volume Sniper: {"⚠️ UNSAFE VALUE ZONE" if data.get('at_value') else "✅ EXTREME VALUE (INSTITUTIONAL)"} (POC: {data.get('poc'):.5f})
• Momentum Sniper: {"✅ IDEAL VELOCITY" if abs(data.get('ema_slope', 0)) < 0.05 else "⚠️ STEEP TREND (RISKY)"} (Slope: {data.get('ema_slope', 0):.4f}%)
• ADR Usage: {data.get('adr_usage')}% {"⚠️ EXHAUSTED" if data.get('adr_exhausted') else "✅ HEALTHY"}

{data.get('news_warning', '')}

⏱ *Expected hold:* 5–20 minutes
⚠️ *Manual execution required*
"""
