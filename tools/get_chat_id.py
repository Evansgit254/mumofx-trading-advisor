import asyncio
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

async def get_chat_id():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    try:
        bot = Bot(token=token)
        print(f"Connecting to bot...")
        me = await bot.get_me()
        print(f"Connected to: @{me.username}")
        print("\nACTION REQUIRED: Please send a message to your bot on Telegram now.")
        print("Waiting for your message...")
        
        # Check for updates every 2 seconds
        while True:
            updates = await bot.get_updates(offset=-1)
            if updates:
                latest_update = updates[-1]
                if latest_update.message:
                    chat_id = latest_update.message.chat_id
                    user_name = latest_update.message.from_user.first_name
                    print(f"\n✅ SUCCESS! Found message from: {user_name}")
                    print(f"Your Chat ID is: {chat_id}")
                    print(f"\nNEXT STEPS:")
                    print(f"1. Update your .env file: TELEGRAM_CHAT_ID={chat_id}")
                    print(f"2. Add TELEGRAM_CHAT_ID to your GitHub Secrets.")
                    return
            await asyncio.sleep(2)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if "Unauthorized" in str(e):
            print("Tip: Check if your Bot Token is correct.")

if __name__ == "__main__":
    asyncio.run(get_chat_id())
