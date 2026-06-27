#!/bin/bash
# =============================================================================
# configure.sh — crypto_trader v6.0 Runtime Configuration
# BTC/USD | Kraken Margin | Vertigo Capital
# Run from ~/crypto-trader/ on EC2
# =============================================================================

SERVICE="cryptobot"
INSTALL_DIR="$HOME/crypto-trader"
CONFIG="$INSTALL_DIR/config.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE}.service"

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

_restart_needed=false

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     crypto_trader v6.0  —  Configure               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_current() {
    local env_line=$(sudo systemctl show $SERVICE --property=Environment)
    local paper=$(echo "$env_line" | grep -o 'PAPER_TRADING=[^ ]*' | cut -d= -f2 | tr -d '"')
    local cash=$(echo "$env_line" | grep -o 'BOT_CASH_BALANCE=[^ ]*' | cut -d= -f2 | tr -d '"')
    local grade_a=$(grep "GRADE_A_NOTIONAL_PCT" $CONFIG | grep -o '[0-9]*\.[0-9]*')
    local grade_b=$(grep "GRADE_B_NOTIONAL_PCT" $CONFIG | grep -o '[0-9]*\.[0-9]*')

    echo -e "${BOLD}  Current Configuration:${NC}"
    echo -e "  Mode:        $([ "$paper" = "True" ] && echo -e "${YELLOW}PAPER${NC}" || echo -e "${RED}LIVE ⚠️${NC}")"
    echo -e "  Cash:        \$$cash"
    echo -e "  Grade A:     $(echo "$grade_a * 100" | bc)% of buying power"
    echo -e "  Grade B:     $(echo "$grade_b * 100" | bc)% of buying power"
    echo ""
}

print_menu() {
    echo -e "${BOLD}  Options:${NC}"
    echo "    1) Toggle paper / live mode"
    echo "    2) Set Grade A size %  (aggressive)"
    echo "    3) Set Grade B size %  (normal)"
    echo "    4) Set paper cash balance"
    echo "    5) Save & exit"
    echo ""
}

toggle_mode() {
    local env_line=$(sudo systemctl show $SERVICE --property=Environment)
    local current=$(echo "$env_line" | grep -o 'PAPER_TRADING=[^ ]*' | cut -d= -f2 | tr -d '"')

    if [ "$current" = "True" ]; then
        # Switching to LIVE
        echo ""
        echo -e "${RED}  ⚠️  WARNING: You are switching to LIVE TRADING${NC}"
        echo -e "${RED}  Real money will be at risk on Kraken.${NC}"
        echo ""
        echo -e "  Run ${BOLD}python report.py${NC} now if you want to save paper trade history."
        echo ""
        printf "  Type LIVE to proceed: "
        read -r confirm
        if [ "$confirm" != "LIVE" ]; then
            echo "  Cancelled — staying in paper mode."
            return
        fi

        # Wipe paper trade data
        echo ""
        echo "  Wiping paper trade data..."
        sudo systemctl stop $SERVICE
        rm -f "$INSTALL_DIR/trades.db" "$INSTALL_DIR/bot.log"
        echo "  Paper data wiped."

        # Update service
        sudo sed -i 's/Environment="PAPER_TRADING=True"/Environment="PAPER_TRADING=False"/' $SERVICE_FILE
        sudo systemctl daemon-reload
        echo -e "  ${GREEN}Mode set to LIVE.${NC}"
    else
        # Switching to PAPER
        printf "  Paper cash balance [1750]: "
        read -r cash
        cash="${cash:-1750}"

        sudo systemctl stop $SERVICE
        rm -f "$INSTALL_DIR/trades.db" "$INSTALL_DIR/bot.log"

        sudo sed -i 's/Environment="PAPER_TRADING=False"/Environment="PAPER_TRADING=True"/' $SERVICE_FILE
        # Update cash balance
        if grep -q "BOT_CASH_BALANCE" $SERVICE_FILE; then
            sudo sed -i "s/Environment=\"BOT_CASH_BALANCE=.*\"/Environment=\"BOT_CASH_BALANCE=$cash\"/" $SERVICE_FILE
        fi
        sudo systemctl daemon-reload
        echo -e "  ${GREEN}Mode set to PAPER | Cash: \$$cash${NC}"
    fi
    _restart_needed=true
}

set_grade_a() {
    echo ""
    local current=$(grep "GRADE_A_NOTIONAL_PCT" $CONFIG | grep -o '[0-9]*\.[0-9]*')
    echo -e "  Current Grade A: $(echo "$current * 100" | bc)%"
    printf "  New Grade A % (e.g. 90 for 90%%): "
    read -r val
    if [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -ge 10 ] && [ "$val" -le 100 ]; then
        local decimal=$(echo "scale=2; $val/100" | bc)
        sed -i "s/GRADE_A_NOTIONAL_PCT.*=.*/GRADE_A_NOTIONAL_PCT      = $decimal/" $CONFIG
        echo -e "  ${GREEN}Grade A set to ${val}%.${NC}"
        _restart_needed=true
    else
        echo "  Invalid — must be between 10 and 100."
    fi
}

set_grade_b() {
    echo ""
    local current=$(grep "GRADE_B_NOTIONAL_PCT" $CONFIG | grep -o '[0-9]*\.[0-9]*')
    echo -e "  Current Grade B: $(echo "$current * 100" | bc)%"
    printf "  New Grade B % (e.g. 75 for 75%%): "
    read -r val
    if [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -ge 10 ] && [ "$val" -le 100 ]; then
        local decimal=$(echo "scale=2; $val/100" | bc)
        sed -i "s/GRADE_B_NOTIONAL_PCT.*=.*/GRADE_B_NOTIONAL_PCT      = $decimal/" $CONFIG
        echo -e "  ${GREEN}Grade B set to ${val}%.${NC}"
        _restart_needed=true
    else
        echo "  Invalid — must be between 10 and 100."
    fi
}

set_cash() {
    echo ""
    local env_line=$(sudo systemctl show $SERVICE --property=Environment)
    local current=$(echo "$env_line" | grep -o 'BOT_CASH_BALANCE=[^ ]*' | cut -d= -f2 | tr -d '"')
    echo -e "  Current cash balance: \$$current"
    printf "  New cash balance (USD): "
    read -r val
    if [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -ge 1 ]; then
        if grep -q "BOT_CASH_BALANCE" $SERVICE_FILE; then
            sudo sed -i "s/Environment=\"BOT_CASH_BALANCE=.*\"/Environment=\"BOT_CASH_BALANCE=$val\"/" $SERVICE_FILE
        else
            sudo sed -i "/\[Service\]/a Environment=\"BOT_CASH_BALANCE=$val\"" $SERVICE_FILE
        fi
        sudo systemctl daemon-reload
        echo -e "  ${GREEN}Cash balance set to \$$val (margin: \$$(echo "$val * 10" | bc)).${NC}"
        _restart_needed=true
    else
        echo "  Invalid amount."
    fi
}

# ── Main loop ─────────────────────────────────────────────────────────────────
print_header
print_current

while true; do
    print_menu
    printf "  Choice: "
    read -r choice

    case $choice in
        1) toggle_mode ;;
        2) set_grade_a ;;
        3) set_grade_b ;;
        4) set_cash ;;
        5)
            if [ "$_restart_needed" = true ]; then
                echo ""
                echo "  Applying changes and restarting bot..."
                sudo systemctl start $SERVICE
                sleep 4
                STATUS=$(systemctl is-active $SERVICE)
                if [ "$STATUS" = "active" ]; then
                    echo -e "  ${GREEN}✅ Bot restarted successfully.${NC}"
                else
                    echo -e "  ${RED}⚠️  Bot failed to start — check: journalctl -u $SERVICE -n 20${NC}"
                fi
            else
                echo "  No changes made."
            fi
            echo ""
            exit 0
            ;;
        *)
            echo "  Invalid choice."
            ;;
    esac

    echo ""
    print_current
done
