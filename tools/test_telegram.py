import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

async def test_telegram_connection():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"📡 Testing Telegram Bot...")
    print(f"Token Found: {'YES' if token else 'NO'}")
    print(f"Chat ID Found: {'YES' if chat_id else 'NO'}")
    
    if not token or not chat_id:
        print("❌ CRITICAL: Missing credentials in .env file.")
        return

    try:
        bot = Bot(token=token)
        message = "🔔 **SYSTEM CHECK**\n\nThe Pro-Trader System is connected and healthy.\nIf you see this, your Bot configuration is CORRECT."
        print(f"Attempting to send to {chat_id}...")
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
        print("✅ Message Sent Successfully!")
    except Exception as e:
        print(f"❌ SEND FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(test_telegram_connection())
