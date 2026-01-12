# TradingExpert: SMC Scalp Signals (Alpha Core)

**Version**: V15.0 (Alpha Core)  
**Status**: Production Ready (Forest Hardened)

## Overview
TradingExpert is an institutional-grade algorithmic trading system designed for scalping major forex pairs (`EURUSD`, `GBPUSD`, `NZDUSD`) and Gold (`GC=F`). It leverages **Smart Money Concepts (SMC)**, **Quantum Displacement**, and **AI-Driven Validation** to identify high-probability setups with a hardcoded confidence threshold of **8.0**.

## Key Features

### 🧠 Alpha Core Logic
- **Liquid Sweeps**: Detects liquidity grabs on M15/H1 timeframes.
- **Quantum Displacement**: Validates momentum with significant body displacement.
- **AI Sentinel**: Google Gemini 2.0 Flash integration for "Institutional Logical" grading.
- **Vectorized Engine**: Full O(N) pre-calculation of FVG, BOS, and Asian Range indicators.

### 🛡️ Risk Management
- **Hardcoded Threshold**: Signals require a minimum confidence score of **8.0/10**.
- **Dynamic Risk**: Session-based position sizing and ATR-based stop losses.
- **News Filter**: Automated washing of high-impact news events (NFP, CPI, FOMC).
- **Portfolio Pruning**: Optimized for a specific basket of high-expectancy assets.

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-repo/TradingExpert.git
   cd TradingExpert
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file with your credentials:
   ```env
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   GEMINI_API_KEY=your_gemini_key
   GITHUB_ACTIONS=false
   ```

## Usage

### Live Scanning
Run the main event loop to monitor markets in real-time:
```bash
python main.py
```

### Backtesting
Run the regression test suite to verify system integrity:
```bash
pytest tests/
```

### Training
Retrain the winning probability model with new data:
```bash
python training/data_collector.py
python training/trainer.py
```

## Performance
- **30-Day Verification**: +13.0R (Pruned Portfolio)
- **Win Rate**: ~65% (on A+ setups)
- **Expectancy**: Positive

## Disclaimer
This software is for educational and research purposes only. Algorithmic trading involves significant risk of capital loss.
