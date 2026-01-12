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

## Deployment
For 24/7 operation on a VPS, use the Docker setup:

1. **Build & Run**:
   ```bash
   docker compose up -d --build
   ```
   
See [DEPLOYMENT.md](DEPLOYMENT.md) for full server setup instructions.

## Performance
- **30-Day Verification**: +13.0R (Pruned Portfolio)
- **Win Rate**: ~41% (High R:R focus)
- **Expectancy**: Positive

## System Trade-offs & Limitations

### 1. Low Win Rate, High R:R
The system is designed for **expectancy**, not accuracy. With a ~41% win rate, you will experience losing streaks. The profitability comes from the >1:2.5 Risk:Reward ratio.
- **Trade-off**: Requires psychological discipline to endure drawdowns.

### 2. Low Frequency (Sniper Approach)
By enforcing a strict **8.0/10 confidence threshold**, the system passes on many "good" trades to wait for "great" ones.
- **Trade-off**: You may see days with **0 trades**. Use this time to study, not force signals.

### 3. Execution Dependency
The logic relies on precise M5 candle closures.
- **Limitation**: Highly sensitive to data feed latency and spread. Not suitable for high-spread brokers or slow VPS environments.

### 4. Complexity vs. Robustness
The multi-layered validation (AI, Correlations, Trend, Structure) reduces false positives but increases system complexity.
- **Limitation**: A failure in one component (e.g., Gemini API outage) can halt the entire pipeline.

## Disclaimer
This software is for educational and research purposes only. Algorithmic trading involves significant risk of capital loss.
