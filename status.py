"""
status.py — Quick bot status check.
Run: python status.py
Instrument-agnostic: reads from config.
"""

import os
import sys
import sqlite3
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET  = ZoneInfo("US/Eastern")
UTC = timezone.utc

# Read install dir and config dynamically
INSTALL_DIR = os.path.expanduser("~/crypto-trader")
sys.path.insert(0, INSTALL_DIR)

try:
    from config import DB_PATH, TRADING_SYMBOL, INSTRUMENT, PAPER_TRADING
    SERVICE_NAME = "cryptobot"
except Exception:
    DB_PATH      = os.path.join(INSTALL_DIR, "trades.db")
    TRADING_SYMBOL = "BTC/USD"
    INSTRUMENT   = "BTC"
    PAPER_TRADING = True
    SERVICE_NAME = "cryptobot"


def now_et():
    return datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")


def to_et(ts):
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(ET).strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return ts[:16]


def sep(char="─", w=52):
    print(char * w)


def check_service():
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True
        )
        status = result.stdout.strip()
        return status == "active", status
    except Exception:
        return False, "unknown"


def get_balance():
    try:
        from data.market_data import get_account_balance
        bal = get_account_balance()
        if bal:
            return bal["USD"]["free"]
    except Exception:
        pass
    return None


def get_regime():
    try:
        log_path = os.path.join(INSTALL_DIR, "bot.log")
        result = subprocess.run(
            ["grep", "-E", "REGIME:|STRATEGY TRANSITION", log_path],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        regime_line = ""
        strategy_line = ""
        for line in reversed(lines):
            if "regime_classifier: REGIME:" in line and not regime_line:
                regime_line = line
            if "STRATEGY TRANSITION:" in line and not strategy_line:
                strategy_line = line
            if regime_line and strategy_line:
                break
        regime   = "UNKNOWN"
        strategy = "UNKNOWN"
        if regime_line:
            parts = regime_line.split("REGIME:")
            if len(parts) > 1:
                regime = parts[1].strip().split()[0]
        if strategy_line:
            parts = strategy_line.split("→")
            if len(parts) > 1:
                strategy = parts[1].strip().split()[0]
        return regime, strategy
    except Exception:
        return "UNKNOWN", "UNKNOWN"


def get_open_trade():
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM trades WHERE status='open' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def get_live_price():
    try:
        from data.market_data import get_current_price
        return get_current_price()
    except Exception:
        return None


def main():
    print()
    sep("═")
    print(f"  {INSTRUMENT} BOT — STATUS")
    print(f"  {now_et()}")
    sep("═")
    print()

    running, status = check_service()
    icon = "🟢" if running else "🔴"
    print(f"  {icon} Service:    {status.upper()}")
    print(f"  📍 Instrument:  {TRADING_SYMBOL}")
    mode = "PAPER" if PAPER_TRADING else "LIVE"
    print(f"  🎯 Mode:        {mode}")

    balance = get_balance()
    if balance:
        print(f"  💵 Cash:       ${balance:,.2f}  (margin: ${balance * 10:,.2f})")
    else:
        print(f"  💵 Cash:       unavailable")

    print()
    sep()

    regime, strategy = get_regime()
    print(f"  📊 Regime:     {regime}")
    print(f"  🎯 Strategy:   {strategy}")

    print()
    sep()

    trade = get_open_trade()
    if trade:
        price = get_live_price()
        entry = trade["entry_price"]
        stop  = trade["stop_price"]
        size  = trade["position_size"]
        dir_  = trade["direction"]
        t1    = trade["target_1"]

        if price:
            risk = abs(entry - stop)
            if dir_ == "long":
                upnl = (price - entry) * size
                r    = (price - entry) / risk if risk else 0
            else:
                upnl = (entry - price) * size
                r    = (entry - price) / risk if risk else 0
        else:
            upnl = 0
            r    = 0

        pnl_icon = "📈" if upnl >= 0 else "📉"
        print(f"  {pnl_icon} OPEN {dir_.upper()}")
        print(f"     Entry:    ${entry:,.2f}")
        if price:
            print(f"     Current:  ${price:,.2f}")
        print(f"     Stop:     ${stop:,.2f}")
        print(f"     Target:   ${t1:,.2f}")
        print(f"     P&L:      ${upnl:+,.2f}  ({r:+.2f}R)")
        print(f"     Grade:    {trade.get('setup_grade','?')}  |  {trade.get('strategy','?')}")
        print(f"     Entered:  {to_et(trade['entry_time'])}")
    else:
        print("  ⏳ No open position")

    print()
    sep("═")
    print()


if __name__ == "__main__":
    main()
