# crypto_trader v6.0 — Vertigo Capital
**BTC/USD | Kraken Margin | Regime-Aware | Auto-Sized | 24/7**

Institutional-grade adaptive trading bot. Classifies market regime every tick and deploys the appropriate strategy. Position sizing is fully automatic based on grade and available buying power. No manual risk inputs required.

---

## Architecture

### Regime Classification
The bot classifies the current market regime on every tick using ATR, ADX, Bollinger Band width, VWAP, and macro context (VIX). Regimes drive strategy selection.

| Regime | Strategy |
|--------|----------|
| TRENDING_BULL / TRENDING_BEAR | MomentumStrategy |
| RANGING | MeanReversion |
| COMPRESSION | CompressionScalp |
| BREAKOUT_VOLATILE | SweepReversal |

### Position Sizing (Auto)
- **Grade A** = 90% of buying power
- **Grade B** = 75% of buying power
- Buying power = cash balance × 10 (10x Kraken margin)
- No circuit breaker — regime reassessment fires after 2 consecutive losses

### Fee Awareness
- Taker fee: 0.80% | Margin open: 0.02% | Rollover: 0.02%
- Trades rejected if 1R < round-trip fees
- Minimum daily range filter: 0.8% (BTC must be moving)

### VWAP Gate
- Hard block on longs below VWAP, shorts above VWAP
- Not a warning — entries are rejected outright

### ADX Stop Multiplier
Applied BEFORE compute_size to preserve dollar risk:
- ADX < 25: 1.0× | 25–40: 1.5× | 40–60: 2.0× | > 60: 2.5×

---

## Deployment

### First-time setup (Windows desktop → fresh EC2)
1. Unpack tarball to `C:\crypto_trader_v6\`
2. Place `tx-9.pem` in `C:\crypto_trader\`
3. Double-click `install.bat`
4. Enter EC2 IP and PEM path
5. Follow `setup_ec2.sh` prompts on EC2

### Diagnostic deployment (validate order flow before production)
Unzip `crypto_trader_v6_diagnostic.zip` to a separate EC2. Runs with:
- `$1` risk per trade
- Relaxed entry gates
- No circuit breaker
- All strategies active

---

## Key Commands

### Service control
```bash
sudo systemctl start cryptobot       # Start
sudo systemctl stop cryptobot        # Stop
sudo systemctl restart cryptobot     # Restart
sudo systemctl status cryptobot      # Service status
```

### Clean restart (wipe trades and log)
```bash
sudo systemctl stop cryptobot
rm -f ~/crypto-trader/bot.log ~/crypto-trader/trades.db
sudo systemctl start cryptobot
```

### Monitoring
```bash
# Live status dashboard
python status.py

# Performance dashboard
python query.py

# Live logs (filtered)
journalctl -u cryptobot -f --no-pager | grep -v DEBUG

# Last 30 lines filtered
journalctl -u cryptobot -n 30 --no-pager | grep -v DEBUG

# Check for errors only
journalctl -u cryptobot -n 50 --no-pager | grep -i error
```

### Debugging
```bash
# Check what the bot is importing
grep -n "from config import" ~/crypto-trader/main.py

# Verify credentials loaded
grep -n "KRAKEN\|TELEGRAM" ~/crypto-trader/credentials.py

# Check Telegram token in service
sudo systemctl cat cryptobot | grep TELEGRAM

# Clear pycache (force fresh imports)
find ~/crypto-trader -name "*.pyc" -delete
find ~/crypto-trader -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# Test Telegram manually
python test_telegram.py

# Run diagnostic report
python diagnostic_report.py
```

### Variable control (config.py)
```bash
# Switch to live trading
sed -i 's/PAPER_TRADING.*=.*/PAPER_TRADING = False/' ~/crypto-trader/config.py

# Check current instrument
grep "TRADING_SYMBOL" ~/crypto-trader/config.py

# Check poll interval
grep "POLL_INTERVAL" ~/crypto-trader/config.py
```

### Account & sizing
```bash
# Check live balance and buying power
python -c "from data.market_data import get_account_balance; b=get_account_balance(); print(b)"

# Check risk manager status
python -c "from risk.risk_manager import get_risk_manager; print(get_risk_manager().status_report())"
```

### Deploy updates from Windows
```bash
# Single file update
scp -i "C:\crypto_trader\tx-9.pem" "C:\crypto_trader_v6\main.py" ubuntu@<EC2_IP>:~/crypto-trader/main.py

# Then restart
sudo systemctl restart cryptobot
```

---

## EC2 Reference

| Bot | IP | Key |
|-----|----|-----|
| BTC v6.0 | 3.139.99.63 | C:\crypto_trader\tx-9.pem |

### SSH
```bash
ssh -i "C:\crypto_trader\tx-9.pem" ubuntu@3.139.99.63
```

---

## Telegram
- **Bot:** @TX9AI_bot
- **Chat ID:** 6075312586
- Alerts: startup, entry, exit, regime change, P&L updates

---

## GitHub
```
https://github.com/TX-9AI/crypto_trader_v6
```

### First push
```bash
git init
git remote add origin https://github.com/TX-9AI/crypto_trader_v6.git
git add .
git commit -m "crypto_trader v6.0 — initial release"
git branch -M main
git push -u origin main
```

### Subsequent pushes
```bash
git add .
git commit -m "describe your change"
git push origin main
```

---

## File Structure
```
crypto_trader_v6/
├── main.py                    # Main loop, regime dispatch, entry/exit
├── config.py                  # All tunable parameters
├── credentials.py.template    # Copy to credentials.py, fill in keys
├── setup_ec2.sh               # EC2 first-time setup script
├── install.bat                # Windows launcher
├── deploy.bat                 # Windows update/restart tool
├── calc.sh                    # Dollar split calculator across bots
├── status.py                  # Live status dashboard
├── query.py                   # Performance dashboard
├── report.py                  # HTML performance report
├── diagnostic_report.py       # Deployment validation report
├── test_telegram.py           # Test Telegram connectivity
├── crypto_trader_v6_diagnostic.zip  # Diagnostic build
├── analysis/                  # Regime, volatility, structure, liquidity
├── data/                      # Market data, macro, cache
├── database/                  # Trade logger, DB manager
├── execution/                 # Entry, exit, position manager, order router
├── notifications/             # Telegram alerts
├── risk/                      # Risk manager, session guard, setup scorer
├── strategy/                  # Momentum, MeanReversion, Compression, Sweep
└── utils/                     # Math, time, startup
```

---

## Session Notes — June 25, 2026
- v6.0 initial deployment on EC2 3.139.99.63
- BTC/USD only, auto-sized from buying power
- Removed: RISK_PER_TRADE_USD, CIRCUIT_BREAKER_PCT, Twilio, Grade C trades
- Added: Telegram via environment variables, yfinance macro data
- Confirmed: regime classification, strategy selection, Telegram alerts firing
