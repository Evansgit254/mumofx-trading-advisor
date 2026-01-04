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
        return f"""
⚡ *SMC SCALP SETUP*

*Pair:* {data['pair']}
*Direction:* {data['direction']}
*Style:* Scalping (SMC)
*Bias TF:* M5
*Entry TF:* M1

*Liquidity Event:*
• {data['liquidity_event']}

*Entry Zone:*
• {data['entry_zone']}

*Stop Loss:*
• {data['sl']:.5f} (below sweep)

*Take Profit:*
• TP1: {data['tp1']:.5f}
• TP2: {data['tp2']:.5f}

*ATR:* {data['atr_status']}
*Session:* {data['session']}
*Confidence:* {data['confidence']} / 10

{data.get('news_warning', '')}

⏱ *Expected hold:* 5–20 minutes
⚠️ *Manual execution required*
"""
