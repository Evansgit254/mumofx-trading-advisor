import os
from dotenv import load_dotenv

load_dotenv()

# Trading Settings
SYMBOLS = ["EURUSD=X", "GBPUSD=X", "NZDUSD=X", "GC=F"] # Pruned Portfolio (Alpha Core)
DXY_SYMBOL = "DX-Y.NYB"
TNX_SYMBOL = "^TNX"
NARRATIVE_TF = "1h"
INSTITUTIONAL_TF = "4h"
STRUCTURE_TF = "15m"
ENTRY_TF = "5m" # Switched to 5m for better intraday consistency
SCALP_TF = "1m"

# CRT settings
CRT_LOOKBACK = 24

# INDICATORS
EMA_TREND = 100 # Optimized from 200
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_AVG_PERIOD = 50
ATR_MULTIPLIER = 1.5 # Optimized from 1.5 (Confirmed)
ADR_PERIOD = 20 # Standard 20-day Average Daily Range
ADR_THRESHOLD_PERCENT = 0.95 # Rebalanced from 0.90 for V5.0
POC_LOOKBACK = 200 # Bars for Volume Profile POC calculation
# LIQUIDITY
LIQUIDITY_LOOKBACK = 50 # bars
SWEEP_WICK_PERCENT = 0.60 # 60%

# ENTRY & EXIT TUNING (V13.0)
BE_TRIGGER_ATR = 0.75 # Move to BE at 0.75 * ATR
PARTIAL_TP_ATR = 0.5 # Take partial at 0.5 * ATR
PARTIAL_SIZE = 0.5 # Close 50% at partial TP

# DISPLACEMENT
DISPLACEMENT_BODY_PERCENT = 0.60 # 60%

# RSI THRESHOLDS
RSI_BUY_LOW = 25
RSI_BUY_HIGH = 40
RSI_SELL_LOW = 60
RSI_SELL_HIGH = 75

# TELEGRAM
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# SESSION TIMES (UTC)
# London: 08:00 - 16:00
# NY: 13:00 - 21:00
LONDON_OPEN = 8
LONDON_CLOSE = 16
NY_OPEN = 13
NY_CLOSE = 21
ASIAN_SESSION_START = 0 # UTC
ASIAN_SESSION_END = 8 # UTC
ASIAN_RANGE_MIN_PIPS = 15 # Minimum range for sweep validity

# NEWS FILTER
NEWS_WASH_ZONE = 30 # Minutes before/after high-impact news
NEWS_IMPACT_LEVELS = ["High", "Medium"] # Impact levels to track

# SCORING (V15.0 Golden Threshold)
MIN_CONFIDENCE_SCORE = 8.0
GOLD_CONFIDENCE_THRESHOLD = 8.0  # V15.1 Balanced (Alpha Core)

# RISK MANAGEMENT V3.2 ($50 Account Optimized)
ACCOUNT_BALANCE = 50.0 # User's target starting balance
RISK_PER_TRADE_PERCENT = 2.0 # Standard 2% risk
MAX_CONCURRENT_TRADES = 2
MIN_LOT_SIZE = 0.01 
