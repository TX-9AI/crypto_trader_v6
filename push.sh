#!/bin/bash
# =============================================================================
# push.sh — Vertigo Capital Git Push Tool
# v1.0 — 2026-06-27 — initial release
#
# Pushes local bot changes to GitHub without exposing token in scripts.
# Token read from systemd service environment or prompted interactively.
#
# Usage:
#   bash push.sh                        — push with auto commit message
#   bash push.sh "your commit message"  — push with custom message
# =============================================================================

BOLD='\033[1m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║     Vertigo Capital — Git Push                      ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

# ── Detect which bot and repo ─────────────────────────────────────────────────
BOT_DIR=""
REPO_URL=""
SERVICE=""

for dir in "$HOME"/*/; do
    [[ "$dir" == *"-deploy"* ]] && continue
    if [ -f "${dir}main.py" ] && [ -f "${dir}config.py" ]; then
        BOT_DIR="${dir%/}"
        break
    fi
done

if [ -z "$BOT_DIR" ]; then
    echo -e "${YELLOW}  ⚠  Could not detect bot directory. Run from bot home.${RESET}"
    exit 1
fi

# Read current remote URL to determine repo
CURRENT_REMOTE=$(cd "$BOT_DIR" && git remote get-url origin 2>/dev/null || echo "")
if echo "$CURRENT_REMOTE" | grep -q "crypto_trader"; then
    SERVICE="cryptobot"
    REPO="crypto_trader_v6"
elif echo "$CURRENT_REMOTE" | grep -q "options_trader"; then
    SERVICE="optionsbot"
    REPO="options_trader_v2"
else
    echo -e "${YELLOW}  ⚠  Could not detect repo from git remote. Is git initialized?${RESET}"
    echo "  Current remote: $CURRENT_REMOTE"
    exit 1
fi

echo -e "  Bot dir: ${BOLD}${BOT_DIR}${RESET}"
echo -e "  Repo:    ${BOLD}https://github.com/TX-9AI/${REPO}${RESET}"
echo -e "  Service: ${BOLD}${SERVICE}${RESET}"
echo ""

# ── Get GitHub token ──────────────────────────────────────────────────────────
TOKEN=$(sudo systemctl show "$SERVICE" --property=Environment 2>/dev/null \
    | grep -o 'GITHUB_TOKEN=[^ ]*' | cut -d= -f2)

if [ -z "$TOKEN" ]; then
    echo -e "  ${YELLOW}GITHUB_TOKEN not in systemd environment.${RESET}"
    read -rsp "  GitHub personal access token: " TOKEN
    echo ""
fi

if [ -z "$TOKEN" ]; then
    echo -e "  ${YELLOW}⚠  No token provided. Aborting.${RESET}"
    exit 1
fi

# ── Stage and commit ──────────────────────────────────────────────────────────
cd "$BOT_DIR"

# Check for changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo -e "  ${GREEN}Nothing to commit — working tree clean.${RESET}"
    exit 0
fi

echo "  Staged changes:"
git status --short
echo ""

COMMIT_MSG="${1:-$(date '+%Y-%m-%d') — patch update}"
git add .
git commit -m "$COMMIT_MSG"

# ── Push with token, then reset URL ──────────────────────────────────────────
git remote set-url origin "https://TX-9AI:${TOKEN}@github.com/TX-9AI/${REPO}.git"
git push origin main
git remote set-url origin "https://github.com/TX-9AI/${REPO}.git"

echo ""
echo -e "  ${GREEN}✅ Pushed to ${REPO} successfully.${RESET}"
echo ""
