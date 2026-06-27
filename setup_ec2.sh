#!/bin/bash
# =============================================================================
# setup_ec2.sh — One-shot crypto-trader deployment script
# Run this on a fresh Ubuntu EC2 instance.
# =============================================================================

set -e
export DEBIAN_FRONTEND=noninteractive
export TERM=xterm-256color

INSTALL_DIR="$HOME/crypto-trader"
DEPLOY_DIR="$HOME/crypto-trader-deploy"
SERVICE_NAME="cryptobot"
VENV="$INSTALL_DIR/venv"

# Redirect stdin from terminal for interactive prompts
exec < /dev/tty

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         crypto-trader — EC2 Setup Script            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Press ENTER to continue or Ctrl+C to cancel."
read -r _

# ─── SYSTEM UPDATE ────────────────────────────────────────────────────────────
echo ""
echo "[ 1/8 ] Updating system packages..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-pip python3-venv git sqlite3 curl rsync

# ─── USER INPUT ───────────────────────────────────────────────────────────────
echo ""
echo "[ 2/8 ] Gathering configuration..."
echo ""

printf "GitHub repo URL (press ENTER to use local files): "; read -r GITHUB_URL
printf "Kraken API Key: "; read -r KRAKEN_KEY
printf "Kraken API Secret: "; read -r KRAKEN_SECRET

echo ""
echo "Twilio SMS alerts (optional — press ENTER to skip):"
printf "  Twilio Account SID: "; read -r TWILIO_SID
printf "  Twilio Auth Token: "; read -r TWILIO_TOKEN
printf "  Twilio From Number (e.g. +18005551234): "; read -r TWILIO_FROM
printf "  Your Phone Number (e.g. +19045551234): "; read -r ALERT_PHONE

echo ""
printf "Bot name [crypto-trader]: "; read -r BOT_NAME
BOT_NAME="${BOT_NAME:-crypto-trader}"

echo ""
echo "Select instrument:"
echo "  1) BTC/USD"
echo "  2) ETH/USD"
echo "  3) SOL/USD"
printf "Choice [1]: "; read -r INSTRUMENT_CHOICE
INSTRUMENT_CHOICE="${INSTRUMENT_CHOICE:-1}"

case "$INSTRUMENT_CHOICE" in
    2) TRADING_SYMBOL="ETH/USD"; KRAKEN_SYMBOL="ETH/USD" ;;
    3) TRADING_SYMBOL="SOL/USD"; KRAKEN_SYMBOL="SOL/USD" ;;
    *) TRADING_SYMBOL="BTC/USD"; KRAKEN_SYMBOL="XBT/USD" ;;
esac

echo ""
echo "Configuration summary:"
echo "  Repo:       ${GITHUB_URL:-local files}"
echo "  Instrument: $TRADING_SYMBOL"
echo "  Bot name:   $BOT_NAME"
echo "  Mode:       PAPER TRADING"
echo ""
echo "Risk per B grade trade in dollars:"
echo "  e.g. 100 = \$100 per B grade trade"
echo "  Minimum \$1 (use small amounts for testing)"
printf "Risk \$ [100]: "; read -r RISK_USD
RISK_USD="${RISK_USD:-100}"
if ! echo "$RISK_USD" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
    echo "  Invalid input — using default 100"
    RISK_USD="100"
fi
RISK_LABEL="\$${RISK_USD} per B grade trade"
echo "  Risk set to: \$$RISK_USD per B grade trade"

echo ""
echo "Circuit breaker threshold — bot STOPS and requires manual restart if"
echo "24hr losses exceed this % of account (e.g. 0.25 = 25%% drawdown):"
printf "Circuit breaker %% [0.25]: "; read -r CB_PCT
CB_PCT="${CB_PCT:-0.25}"
if ! echo "$CB_PCT" | grep -qE '^0\.[0-9]+$'; then
    echo "  Invalid input — using default 0.25"
    CB_PCT="0.25"
fi
echo "  Circuit breaker set to: $CB_PCT (bot stops at this drawdown)" 

echo ""
printf "Looks good? Press ENTER to continue or Ctrl+C to cancel: "; read -r _

# ─── PROJECT FILES ────────────────────────────────────────────────────────────
echo ""
echo "[ 3/8 ] Setting up project files..."

if [ -n "$GITHUB_URL" ]; then
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "  Pulling latest from GitHub..."
        cd "$INSTALL_DIR" && git pull origin master
    else
        rm -rf "$INSTALL_DIR"
        git clone "$GITHUB_URL" "$INSTALL_DIR"
    fi
else
    echo "  Copying local files from deploy directory..."
    mkdir -p "$INSTALL_DIR"
    rsync -a \
        --exclude='.git' \
        --exclude='*.pem' \
        --exclude='credentials.py' \
        --exclude='venv' \
        --exclude='trades.db' \
        --exclude='bot.log' \
        --exclude='__pycache__' \
        "$DEPLOY_DIR/" "$INSTALL_DIR/"
    echo "  Files copied."
fi

cd "$INSTALL_DIR"
chmod +x configure.sh setup_ec2.sh 2>/dev/null || true

# Verify critical files exist
for f in main.py config.py utils/time_utils.py strategy/momentum_strategy.py; do
    [ -f "$f" ] || { echo "ERROR: $f missing from install. Aborting."; exit 1; }
done
echo "  File verification passed."

# ─── PYTHON ENVIRONMENT ───────────────────────────────────────────────────────
echo ""
echo "[ 4/8 ] Creating Python virtual environment..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --upgrade pip -q
pip install ccxt twilio pandas numpy tzdata yfinance -q
echo "  Dependencies installed."

# ─── GENERATE CREDENTIALS ─────────────────────────────────────────────────────
echo ""
echo "[ 5/8 ] Generating credentials.py..."

cat > "$INSTALL_DIR/credentials.py" << CREDEOF
"""
credentials.py — Generated by setup_ec2.sh on $(date)
DO NOT commit this file to GitHub.
"""

KRAKEN_API_KEY     = "$KRAKEN_KEY"
KRAKEN_API_SECRET  = "$KRAKEN_SECRET"

TWILIO_ACCOUNT_SID = "$TWILIO_SID"
TWILIO_AUTH_TOKEN  = "$TWILIO_TOKEN"
TWILIO_FROM_NUMBER = "$TWILIO_FROM"
ALERT_TO_PHONE     = "$ALERT_PHONE"

BOT_NAME           = "$BOT_NAME"

SENDGRID_API_KEY   = ""
ALERT_FROM_EMAIL   = ""
ALERT_TO_EMAIL     = ""
CREDEOF

chmod 600 "$INSTALL_DIR/credentials.py"
echo "  credentials.py created."

# ─── CONFIGURE INSTRUMENT ─────────────────────────────────────────────────────
echo ""
echo "[ 6/8 ] Configuring instrument ($TRADING_SYMBOL)..."

cd "$INSTALL_DIR"
sed -i 's|^TRADING_SYMBOL = "BTC/USD".*|# TRADING_SYMBOL = "BTC/USD"; KRAKEN_SYMBOL = "XBT/USD:BTNL"|g' config.py
sed -i 's|^TRADING_SYMBOL = "ETH/USD".*|# TRADING_SYMBOL = "ETH/USD"; KRAKEN_SYMBOL = "ETH/USD:BTNL"|g' config.py
sed -i 's|^TRADING_SYMBOL = "SOL/USD".*|# TRADING_SYMBOL = "SOL/USD"; KRAKEN_SYMBOL = "SOL/USD:BTNL"|g' config.py

if [ "$TRADING_SYMBOL" = "ETH/USD" ]; then
    sed -i 's|^# TRADING_SYMBOL = "ETH/USD".*|TRADING_SYMBOL = "ETH/USD"; KRAKEN_SYMBOL = "ETH/USD:BTNL"|g' config.py
elif [ "$TRADING_SYMBOL" = "SOL/USD" ]; then
    sed -i 's|^# TRADING_SYMBOL = "SOL/USD".*|TRADING_SYMBOL = "SOL/USD"; KRAKEN_SYMBOL = "SOL/USD:BTNL"|g' config.py
else
    sed -i 's|^# TRADING_SYMBOL = "BTC/USD".*|TRADING_SYMBOL = "BTC/USD"; KRAKEN_SYMBOL = "XBT/USD:BTNL"|g' config.py
fi

sed -i 's|^PAPER_TRADING.*|PAPER_TRADING             = True|g' config.py
sed -i "s|^RISK_PER_TRADE_USD.*|RISK_PER_TRADE_USD        = $RISK_USD|g" config.py
echo "  config.py updated."

# ─── SYSTEMD SERVICE ──────────────────────────────────────────────────────────
echo ""
echo "[ 7/8 ] Creating systemd service..."

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << SVCEOF
[Unit]
Description=Crypto Adaptive Trading Bot ($BOT_NAME)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$INSTALL_DIR
ExecStartPre=/bin/bash -c 'touch $INSTALL_DIR/bot.log $INSTALL_DIR/trades.db; chown ubuntu:ubuntu $INSTALL_DIR/bot.log $INSTALL_DIR/trades.db; chmod 644 $INSTALL_DIR/bot.log $INSTALL_DIR/trades.db'
ExecStartPre=/bin/bash -c 'touch /home/ubuntu/crypto-trader/bot.log /home/ubuntu/crypto-trader/trades.db; chown ubuntu:ubuntu /home/ubuntu/crypto-trader/bot.log /home/ubuntu/crypto-trader/trades.db; chmod 644 /home/ubuntu/crypto-trader/bot.log /home/ubuntu/crypto-trader/trades.db'
ExecStart=$VENV/bin/python main.py --service
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

sudo tee /etc/logrotate.d/$SERVICE_NAME > /dev/null << LOGEOF
$INSTALL_DIR/bot.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
LOGEOF

# ─── BASH PROFILE ─────────────────────────────────────────────────────────────
grep -q "crypto-trader/venv" ~/.bashrc || echo "source $VENV/bin/activate" >> ~/.bashrc
grep -q "cd ~/crypto-trader" ~/.bashrc || echo "cd $INSTALL_DIR" >> ~/.bashrc

# ─── START BOT ────────────────────────────────────────────────────────────────
echo ""
echo "[ 8/8 ] Starting bot..."

touch "$INSTALL_DIR/bot.log" "$INSTALL_DIR/trades.db"
chown ubuntu:ubuntu "$INSTALL_DIR/bot.log" "$INSTALL_DIR/trades.db" "$INSTALL_DIR/credentials.py"
chmod 644 "$INSTALL_DIR/bot.log" "$INSTALL_DIR/trades.db"
chmod 600 "$INSTALL_DIR/credentials.py"

sudo systemctl start $SERVICE_NAME
sleep 10

STATUS=$(systemctl is-active $SERVICE_NAME)
if [ "$STATUS" = "active" ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║              ✅  Setup Complete!                    ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "  Bot:        $BOT_NAME"
    echo "  Instrument: $TRADING_SYMBOL"
    echo "  Mode:       PAPER TRADING"
    echo "  Service:    $SERVICE_NAME"
    echo "  Install:    $INSTALL_DIR"
    echo ""
    echo "  Commands:"
    echo "    python status.py    — check status"
    echo "    python query.py     — performance dashboard"
    echo "    tail -f bot.log     — live log"
    echo "    ./configure.sh      — change instrument or go live"
    echo ""
    source "$VENV/bin/activate" && python status.py
else
    echo ""
    echo "  ⚠️  Service did not start correctly."
    echo "  Check: journalctl -u $SERVICE_NAME -n 30 --no-pager"
    echo "  Check: tail -20 $INSTALL_DIR/bot.log"
fi
