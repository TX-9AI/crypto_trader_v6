#!/bin/bash
# =============================================================================
# setup_ec2.sh — crypto_trader v6.1 EC2 Setup
# v1.0 — original release (Twilio, credentials.py)
# v2.1 — 2026-06-27 — print session activation instructions after install
# v2.0 — 2026-06-27 — Telegram only, no credentials.py, environment-based
#         secrets, GitHub repo/token prompt, git init, matches options_trader
#         setup style
#
# BTC/USD | Kraken Margin | Telegram alerts
# =============================================================================

set -e
export DEBIAN_FRONTEND=noninteractive
export TERM=xtext-256color

INSTALL_DIR="$HOME/crypto-trader"
DEPLOY_DIR="$HOME/crypto-trader-deploy"
SERVICE_NAME="cryptobot"
VENV="$INSTALL_DIR/venv"
VERSION="6.0"

exec < /dev/tty

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'

print_step() { echo -e "\n${BOLD}${GREEN}[ $1 ]${RESET} $2"; }
print_ok()   { echo -e "  ${GREEN}✓${RESET}  $1"; }
print_info() { echo -e "  ${CYAN}→${RESET}  $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
ask()        { read -rp "    $1: " "$2"; }
ask_secret() { read -rsp "    $1 (paste, then ENTER): " "$2"; echo ""; }
ask_yn()     {
    while true; do
        read -rp "    $1 [y/n]: " yn
        case "$yn" in [Yy]) return 0;; [Nn]) return 1;; esac
    done
}

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║     crypto_trader v${VERSION}  |  Vertigo Capital      ║${RESET}"
echo -e "${BOLD}${CYAN}║     BTC/USD  |  Kraken Margin  |  Telegram          ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
echo "  Have ready:"
echo "    - Kraken API Key & Secret"
echo "    - Telegram Bot Token & Chat ID"
echo "    - GitHub Personal Access Token (optional)"
echo ""
read -rp "  Press ENTER to continue or Ctrl+C to cancel..."

# ─── STEP 1: TRADING MODE ────────────────────────────────────────────────────
print_step "1/8" "Trading Mode"
echo ""
PAPER_TRADING="True"
RISK_USD="100"

printf "    Paper trading? [Y/n, default=Y]: "; read -r PAPER_INPUT
PAPER_INPUT="${PAPER_INPUT:-Y}"
if [[ "$PAPER_INPUT" =~ ^[Nn] ]]; then
    PAPER_TRADING="False"
    print_warn "LIVE TRADING — real orders will be sent to Kraken"
else
    PAPER_TRADING="True"
    print_ok "Paper mode"
fi

printf "    Risk per trade USD [100]: "; read -r RISK_INPUT
RISK_USD="${RISK_INPUT:-100}"
if ! echo "$RISK_USD" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
    print_warn "Invalid — using default 100"
    RISK_USD="100"
fi
print_ok "Risk: \$${RISK_USD}/trade | Mode: $([ "$PAPER_TRADING" = "True" ] && echo "PAPER" || echo "LIVE")"

# ─── STEP 2: KRAKEN CREDENTIALS ──────────────────────────────────────────────
print_step "2/8" "Kraken API Credentials"
echo ""
echo -e "  Get from: kraken.com → Security → API → Add Key"
echo -e "  Permissions needed: Query, Create/Modify Orders, Query Open Orders"
echo ""
while true; do
    ask_secret "Kraken API Key" KRAKEN_KEY
    [[ -n "$KRAKEN_KEY" ]] && break
    print_warn "Cannot be empty."
done
while true; do
    ask_secret "Kraken API Secret" KRAKEN_SECRET
    [[ -n "$KRAKEN_SECRET" ]] && break
    print_warn "Cannot be empty."
done
print_ok "Kraken credentials accepted."

# ─── STEP 3: TELEGRAM ────────────────────────────────────────────────────────
print_step "3/8" "Telegram Alerts"
echo ""
while true; do
    ask_secret "Telegram Bot Token" TELEGRAM_TOKEN
    [[ -n "$TELEGRAM_TOKEN" ]] && break
    print_warn "Cannot be empty."
done
while true; do
    ask "Telegram Chat ID" TELEGRAM_CHAT_ID
    [[ -n "$TELEGRAM_CHAT_ID" ]] && break
    print_warn "Cannot be empty."
done
print_ok "Telegram configured."

# ─── STEP 4: GITHUB REPO & TOKEN ─────────────────────────────────────────────
print_step "4/8" "GitHub Repository (optional)"
echo ""
echo -e "  Enter the GitHub repo to link this server to for push.sh."
echo -e "  Format: TX-9AI/crypto_trader_v6"
echo -e "  Press ENTER to skip."
echo ""
GITHUB_REPO=""
GITHUB_TOKEN=""
printf "    GitHub repo [ENTER to skip]: "; read -r GITHUB_REPO

if [[ -n "$GITHUB_REPO" ]]; then
    echo ""
    echo -e "  Get token from: github.com → Settings → Developer settings → Tokens (classic)"
    echo ""
    while true; do
        ask_secret "GitHub Personal Access Token" GITHUB_TOKEN
        [[ -n "$GITHUB_TOKEN" ]] && break
        print_warn "Cannot be empty."
    done
    print_ok "GitHub repo: https://github.com/${GITHUB_REPO}"
    print_ok "GitHub token accepted."
else
    print_ok "Skipping GitHub — push.sh will prompt for token when needed."
fi

# ─── STEP 5: SYSTEM PACKAGES ─────────────────────────────────────────────────
print_step "5/8" "System packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv python-is-python3 git rsync bc sqlite3 curl
print_ok "System packages ready."

# ─── STEP 6: INSTALL FILES ───────────────────────────────────────────────────
print_step "6/8" "Installing bot files"
mkdir -p "$INSTALL_DIR"
rsync -a \
    --exclude='.git' \
    --exclude='*.pem' \
    --exclude='*.bat' \
    --exclude='credentials.py' \
    --exclude='venv' \
    --exclude='trades.db' \
    --exclude='trades.db-shm' \
    --exclude='trades.db-wal' \
    --exclude='bot.log' \
    --exclude='__pycache__' \
    "$DEPLOY_DIR/" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/configure.sh" "$INSTALL_DIR/push.sh" "$INSTALL_DIR/snapshot.sh" 2>/dev/null || true

for f in main.py config.py requirements.txt; do
    [ -f "$INSTALL_DIR/$f" ] || { echo "ERROR: $f missing. Aborting."; exit 1; }
done
print_ok "Files installed to ${INSTALL_DIR}"

# ─── STEP 7: PYTHON ENVIRONMENT ──────────────────────────────────────────────
print_step "7/8" "Python environment"
python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --upgrade pip -q
pip install -r "$INSTALL_DIR/requirements.txt" -q
pip install ccxt pandas numpy tzdata yfinance requests -q
print_ok "Dependencies installed."

grep -q "crypto-trader/venv" ~/.bashrc || echo "source $VENV/bin/activate" >> ~/.bashrc
grep -q "cd ~/crypto-trader"  ~/.bashrc || echo "cd $INSTALL_DIR"           >> ~/.bashrc

# ─── STEP 8: SYSTEMD SERVICE ─────────────────────────────────────────────────
print_step "8/8" "Configuring systemd service"

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << SVCEOF
[Unit]
Description=crypto_trader v${VERSION} — BTC/USD | Vertigo Capital
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
Environment=PAPER_TRADING=${PAPER_TRADING}
Environment=RISK_PER_TRADE_USD=${RISK_USD}
Environment=KRAKEN_API_KEY=${KRAKEN_KEY}
Environment=KRAKEN_API_SECRET=${KRAKEN_SECRET}
Environment=TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
Environment=TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
Environment=GITHUB_TOKEN=${GITHUB_TOKEN}
Environment=GITHUB_REPO=${GITHUB_REPO}
ExecStartPre=/bin/bash -c 'touch ${INSTALL_DIR}/bot.log ${INSTALL_DIR}/trades.db && chown ${USER}:${USER} ${INSTALL_DIR}/bot.log ${INSTALL_DIR}/trades.db'
ExecStart=${VENV}/bin/python main.py --service
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
SVCEOF

sudo chmod 600 /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

touch "$INSTALL_DIR/bot.log" "$INSTALL_DIR/trades.db"
chown "${USER}:${USER}" "$INSTALL_DIR/bot.log" "$INSTALL_DIR/trades.db"

# ── Git init ──────────────────────────────────────────────────────────────────
cd "$INSTALL_DIR"
if [ ! -d ".git" ]; then
    git init -q
    git branch -M main 2>/dev/null || git checkout -b main 2>/dev/null || true
    if [[ -n "$GITHUB_REPO" ]]; then
        git remote add origin "https://github.com/${GITHUB_REPO}.git"
        git fetch origin main -q 2>/dev/null || true
        git reset --hard origin/main -q 2>/dev/null || true
        print_ok "Git repo initialized — push.sh ready to use"
    else
        print_ok "Git initialized — add remote manually when ready"
    fi
fi

# ── Start bot ─────────────────────────────────────────────────────────────────
print_info "Starting bot..."
sudo systemctl start ${SERVICE_NAME}
sleep 8

STATUS=$(systemctl is-active ${SERVICE_NAME})
if [ "$STATUS" = "active" ]; then
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${GREEN}║          ✅  Setup Complete — Bot Running!          ║${RESET}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "  Instrument:  BTC/USD (Kraken Margin)"
    echo -e "  Mode:        $([ "$PAPER_TRADING" = "True" ] && echo "📄 PAPER" || echo "🔴 LIVE")"
    echo -e "  Risk:        \$${RISK_USD}/trade"
    echo -e "  Telegram:    chat ${TELEGRAM_CHAT_ID}"
    echo ""
    echo -e "  Commands:"
    echo -e "    python status.py                   — live status"
    echo -e "    python query.py                    — performance dashboard"
    echo -e "    journalctl -u ${SERVICE_NAME} -f   — live logs"
    echo -e "    bash configure.sh                  — change settings"
    echo -e "    bash push.sh                       — push changes to GitHub"
    echo -e "    bash snapshot.sh                   — snapshot bot state"
    echo ""
    source "${VENV}/bin/activate" && python "$INSTALL_DIR/status.py"
else
    echo ""
    echo -e "${BOLD}${YELLOW}⚠️  Service did not start. Check:${RESET}"
    echo -e "    journalctl -u ${SERVICE_NAME} -n 30 --no-pager"
    echo ""
    journalctl -u ${SERVICE_NAME} -n 20 --no-pager
fi

echo ""
echo -e "  ${BOLD}Run these to activate your session:${RESET}"
echo -e "    source ~/crypto-trader/venv/bin/activate"
echo -e "    cd ~/crypto-trader"
echo ""
echo ""
echo -e "  ${BOLD}Session setup:${RESET}"
echo -e "    source ~/crypto-trader/venv/bin/activate"
echo -e "    cd ~/crypto-trader"
echo ""
echo -e "  These are already saved to ~/.bashrc — new SSH sessions activate automatically."
echo ""
