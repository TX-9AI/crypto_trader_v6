#!/bin/bash
# =============================================================================
# install.sh — crypto_trader v6.0 Web Installer
# v1.0 — original release (inline, credentials.py, Twilio)
# v2.0 — 2026-06-27 — clones repo, calls setup_ec2.sh, sources venv after
# v2.1 — 2026-06-27 — removed set -e so venv activation always runs
#
# Run on a fresh EC2:
#   curl -fsSL https://raw.githubusercontent.com/TX-9AI/crypto_trader_v6/main/install.sh -o install.sh && bash install.sh
# =============================================================================

REPO="https://github.com/TX-9AI/crypto_trader_v6.git"
DEPLOY_DIR="$HOME/crypto-trader-deploy"
INSTALL_DIR="$HOME/crypto-trader"
VENV="$INSTALL_DIR/venv"

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

# Run setup
chmod +x "$DEPLOY_DIR/setup_ec2.sh"
bash "$DEPLOY_DIR/setup_ec2.sh"


