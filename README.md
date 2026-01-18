# Bags.fm Coin Detection Telegram Bot

A sophisticated Telegram bot that monitors Solana tokens (especially those launched on [Bags.fm](https://bags.fm)), analyzes them for promising patterns, and sends real-time alerts when potential opportunities are detected.

## Features

- **Real-time Token Discovery**: Scans DexScreener for new and trending Solana tokens
- **Bags.fm Integration**: Identifies and prioritizes tokens launched on Bags.fm
- **Pattern Detection**: Analyzes 15+ patterns including:
  - Volume surges and acceleration
  - Liquidity depth analysis
  - Price momentum indicators
  - Buy/sell pressure analysis
  - AI/tech theme detection (based on successful Bags.fm tokens like GAS, RALPH, CMEM, VVM)
- **Smart Scoring**: 0-100 scoring system with letter grades (A-F)
- **Telegram Alerts**: Beautiful formatted alerts with all key metrics
- **Database Tracking**: SQLite database tracks token history, scores, and performance
- **Rate Limiting**: Respects API rate limits for reliable operation

## Pattern Analysis

Based on analysis of successful Bags.fm tokens, the bot looks for:

| Pattern | Description | Score Impact |
|---------|-------------|--------------|
| Volume Surge | 5x+ volume spike in last hour | +30 |
| Strong Momentum | Price up >5% (1h) and >20% (24h) | +25 |
| AI/Tech Theme | Token name matches AI keywords | +20 |
| Strong Liquidity | Liquidity >$50K | +20 |
| Buying Pressure | Buy/sell ratio >2:1 | +20 |
| Bags.fm Verified | Confirmed Bags.fm launch | +15 |
| High Creator Earnings | >$100K in creator fees | +25 |

## Installation

### Prerequisites

- Python 3.10+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Telegram Chat/Channel ID

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/bags-coin-detection-bot.git
cd bags-coin-detection-bot
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run the bot:
```bash
python main.py
```

## Configuration

### Required Environment Variables

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id_or_channel_id
```

### Optional Settings

```env
# Bags.fm API (for enhanced data)
BAGS_API_KEY=your_bags_api_key

# Alert Thresholds
MIN_LIQUIDITY_USD=5000      # Minimum liquidity to alert
MIN_VOLUME_24H=10000        # Minimum 24h volume
MIN_SCORE=60                # Minimum score to trigger alert

# Scan Intervals (seconds)
SCAN_INTERVAL_NEW_PAIRS=60  # How often to check for new tokens
```

## Alert Format

```
🚨 NEW TOKEN ALERT 🚨

🅰️ Token Name ($SYMBOL) 🎒 BAGS.FM

📊 Score: 85/100 | Grade: A

💰 Price: $0.00001234
💎 Market Cap: $500,000
💧 Liquidity: $75,000
📈 24h Volume: $150,000
📈 24h Change: +45.5%
⏱ 12.5h old

Score Breakdown:
  📊 Pattern: 32/40
  💧 Liquidity: 15/20
  📈 Volume: 18/20
  🚀 Momentum: 20/20
  ⚠️ Risk: 0

Key Signals:
  • Strong AI/tech theme: matches ai, agent
  • Volume surge in last hour
  • Strong buying pressure: 2.5x more buys than sells

🔗 DexScreener
📋 TokenAddress123...
```

## Architecture

```
src/
├── api/
│   ├── dexscreener.py    # DexScreener API client
│   └── bags.py           # Bags.fm API client
├── analysis/
│   ├── patterns.py       # Pattern detection algorithms
│   └── scorer.py         # Token scoring system
├── bot/
│   ├── telegram_bot.py   # Telegram bot & alerts
│   └── formatter.py      # Message formatting
├── database/
│   └── tracker.py        # SQLite tracking
├── utils/
│   └── helpers.py        # Utility functions
├── config.py             # Configuration management
└── scanner.py            # Main scanner orchestration
```

## API Endpoints Used

### DexScreener (free tier)
- `GET /token-boosts/latest/v1` - Recently boosted tokens
- `GET /token-boosts/top/v1` - Top boosted tokens
- `GET /latest/dex/search` - Search for tokens
- `GET /token-pairs/v1/{chain}/{address}` - Get token pairs

### Bags.fm (optional)
- `GET /token-launch/lifetime-fees` - Creator earnings
- `GET /token-launch/creator` - Creator info

## Scoring System

Tokens are scored 0-100 based on:

| Component | Max Points | Description |
|-----------|-----------|-------------|
| Pattern Score | 40 | Detected bullish/bearish patterns |
| Liquidity Score | 20 | Pool depth analysis |
| Volume Score | 20 | Trading activity |
| Momentum Score | 20 | Price action & buy pressure |
| Risk Penalty | -30 | Deductions for red flags |

### Alert Levels

- **High (🚨)**: Score 80+ or volume surge with score 70+
- **Medium (⚠️)**: Score 70+
- **Low (📊)**: Score 60+

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This bot is for informational purposes only. Cryptocurrency trading involves significant risk. Always do your own research (DYOR) before making any investment decisions. The creators of this bot are not responsible for any financial losses.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [DexScreener](https://dexscreener.com) for their excellent API
- [Bags.fm](https://bags.fm) for pioneering creator coins on Solana
- [python-telegram-bot](https://python-telegram-bot.org/) for the Telegram integration
