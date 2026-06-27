#!/bin/bash
# =============================================================================
# install.sh — crypto_trader v6.0 Web Installer
# v1.0 — original release (inline setup, credentials.py, Twilio)
# v2.0 — 2026-06-27 — clones repo and calls setup_ec2.sh, matches
# v2.1 — 2026-06-27 — activate venv and cd in install.sh after setup completes
#         options_trader install pattern
#
# Run on a fresh EC2:
#   curl -fsSL https://raw.githubusercontent.com/TX-9AI/crypto_trader_v6/main/install.sh -o install.sh && bash install.sh
# =============================================================================

set -e

REPO="https://github.com/TX-9AI/crypto_trader_v6.git"
DEPLOY_DIR="$HOME/crypto-trader-deploy"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     crypto_trader v6.0  |  Web Installer            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Install git if needed
sudo apt-get update -qq
sudo apt-get install -y -qq git

# Clone or update repo into deploy dir
if [ -d "$DEPLOY_DIR/.git" ]; then
    echo "  Updating existing repo..."
    cd "$DEPLOY_DIR" && git pull
else
    echo "  Cloning repository..."
    git clone "$REPO" "$DEPLOY_DIR"
fi

echo "  Repository ready."
echo ""

# Run setup from the deploy dir
chmod +x "$DEPLOY_DIR/setup_ec2.sh"
bash "$DEPLOY_DIR/setup_ec2.sh"

# Activate venv and cd into install dir in the current terminal session
INSTALL_DIR="$HOME/crypto-trader"
VENV="$INSTALL_DIR/venv"
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    cd "$INSTALL_DIR"
fi
