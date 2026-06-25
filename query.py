"""
query.py — Crypto Bot Performance Dashboard
Instrument-agnostic: reads INSTRUMENT and TRADING_SYMBOL from config.
"""

import sqlite3
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

INSTALL_DIR = os.path.expanduser("~/crypto-trader")
sys.path.insert(0, INSTALL_DIR)

try:
    from config import DB_PATH, TRADING_SYMBOL, INSTRUMENT
except Exception:
    DB_PATH      = os.path.join(INSTALL_DIR, "trades.db")
    TRADING_SYMBOL = "BTC/USD"
    INSTRUMENT   = "BTC"

ET  = ZoneInfo("US/Eastern")
UTC = timezone.utc


def connect():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def to_et(ts: str) -> str:
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(ET).strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        return ts[:16]


def now_et():
    return datetime.now(ET)


def get_live_price():
    try:
        from data.market_data import get_current_price
        return get_current_price()
    except Exception as e:
        return None


def pnl_color(val):
    return f"+${val:.2f}" if val >= 0 else f"-${abs(val):.2f}"


def bar(pct, width=20):
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def sep(char="─", width=62):
    print(char * width)


def today_et_prefix():
    return now_et().strftime("%Y-%m-%d")


def show_open_position(conn):
    row = conn.execute(
        "SELECT * FROM trades WHERE status='open' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    sep("═")
    print("  OPEN POSITION")
    sep("═")

    if not row:
        print("  No open position.")
        print()
        return

    price = get_live_price()
    entry = row["entry_price"]
    stop  = row["stop_price"]
    size  = row["position_size"]
    dir_  = row["direction"].upper()
    t1    = row["target_1"]
    t2    = row["target_2"] or 0

    if price:
        risk = abs(entry - stop)
        if row["direction"] == "long":
            upnl   = (price - entry) * size
            r_mult = (price - entry) / risk if risk else 0
        else:
            upnl   = (entry - price) * size
            r_mult = (entry - price) / risk if risk else 0
    else:
        upnl   = 0
        r_mult = 0

    partial_pnl = row["partial_pnl_usd"] or 0
    total_pnl   = upnl + partial_pnl

    print(f"  ID:          {row['trade_id'][:8]}")
    print(f"  Direction:   {dir_}")
    print(f"  Instrument:  {TRADING_SYMBOL}")
    print(f"  Strategy:    {row['strategy']}  |  Grade: {row['setup_grade']}")
    print(f"  Regime:      {row['regime']}")
    print(f"  Entry:       ${entry:,.2f}")
    if price:
        print(f"  Current:     ${price:,.2f}")
    print(f"  Stop:        ${stop:,.2f}")
    print(f"  Target 1:    ${t1:,.2f}")
    if t2:
        print(f"  Target 2:    ${t2:,.2f}")
    print(f"  Size:        {size:.4f} {INSTRUMENT}")
    print(f"  Risk $:      ${row['risk_usd']:.2f}")
    print(f"  Unrealized:  {pnl_color(upnl)}")
    if partial_pnl:
        print(f"  Partial P&L: {pnl_color(partial_pnl)}")
    print(f"  Total P&L:   {pnl_color(total_pnl)}")
    print(f"  R-Multiple:  {r_mult:+.2f}R")
    print(f"  Paper:       {'Yes' if row['paper_trade'] else 'No'}")
    print(f"  Entered:     {to_et(row['entry_time'])}")
    print()


def show_today(conn):
    today = today_et_prefix()
    # entry_time stored as UTC — trades after 8PM ET have UTC date = next day
    # Convert UTC to ET (subtract 4 hours) before date comparison
    rows = conn.execute(
        "SELECT * FROM trades WHERE status='closed' AND date(datetime(entry_time, '-4 hours')) = ? ORDER BY exit_time",
        (today,)
    ).fetchall()

    sep()
    print(f"  TODAY'S TRADES  ({today} ET)")
    sep()

    if not rows:
        print("  No closed trades today.")
        print()
        return

    wins   = [r for r in rows if r["pnl_usd"] > 0]
    losses = [r for r in rows if r["pnl_usd"] <= 0]
    total  = sum(r["pnl_usd"] for r in rows)
    win_rt = len(wins) / len(rows) * 100 if rows else 0

    print(f"  Trades:      {len(rows)}  ({len(wins)}W / {len(losses)}L)")
    print(f"  Win Rate:    {win_rt:.0f}%")
    print(f"  Net P&L:     {pnl_color(total)}")
    if wins:
        print(f"  Best Trade:  {pnl_color(max(r['pnl_usd'] for r in wins))}")
    if losses:
        print(f"  Worst Trade: {pnl_color(min(r['pnl_usd'] for r in losses))}")
    print()

    print(f"  {'ID':<10} {'Dir':<6} {'Grade':<6} {'Entry':>10} {'Exit':>10} {'P&L':>10} {'R':>6}  {'Time (ET)'}")
    sep()
    for r in rows:
        print(
            f"  {r['trade_id'][:8]:<10} "
            f"{r['direction'].upper():<6} "
            f"{r['setup_grade'] or '?':<6} "
            f"${r['entry_price']:>9,.0f} "
            f"${r['exit_price']:>9,.0f} "
            f"{pnl_color(r['pnl_usd']):>10} "
            f"{r['pnl_r']:>+5.2f}R  "
            f"{to_et(r['exit_time'])}"
        )
    print()


def show_alltime(conn):
    rows = conn.execute(
        "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time"
    ).fetchall()

    sep()
    print("  ALL-TIME PERFORMANCE")
    sep()

    if not rows:
        print("  No closed trades yet.")
        print()
        return

    wins      = [r for r in rows if r["pnl_usd"] > 0]
    losses    = [r for r in rows if r["pnl_usd"] <= 0]
    total_pnl = sum(r["pnl_usd"] for r in rows)
    win_rate  = len(wins) / len(rows) * 100 if rows else 0
    avg_win   = sum(r["pnl_usd"] for r in wins) / len(wins) if wins else 0
    avg_loss  = sum(r["pnl_usd"] for r in losses) / len(losses) if losses else 0
    avg_r     = sum(r["pnl_r"] for r in rows) / len(rows) if rows else 0
    profit_factor = (
        abs(sum(r["pnl_usd"] for r in wins) / sum(r["pnl_usd"] for r in losses))
        if losses and sum(r["pnl_usd"] for r in losses) != 0 else 0
    )

    running = peak = max_dd = 0.0
    for r in rows:
        running += r["pnl_usd"]
        peak     = max(peak, running)
        max_dd   = max(max_dd, peak - running)

    print(f"  Total Trades:    {len(rows)}  ({len(wins)}W / {len(losses)}L)")
    print(f"  Win Rate:        {win_rate:.1f}%  {bar(win_rate)}")
    print(f"  Net P&L:         {pnl_color(total_pnl)}")
    print(f"  Avg Win:         {pnl_color(avg_win)}")
    print(f"  Avg Loss:        {pnl_color(avg_loss)}")
    print(f"  Avg R/Trade:     {avg_r:+.2f}R")
    total_fees = sum(r["commission_usd"] or 0 for r in rows)
    adj_pnl    = sum((r["pnl_usd"] or 0) - (r["commission_usd"] or 0) for r in rows)
    print(f"  Est Fees Paid:   ${total_fees:.2f}")
    print(f"  Fee-Adj P&L:     {pnl_color(adj_pnl)}")
    print(f"  Profit Factor:   {profit_factor:.2f}")
    print(f"  Max Drawdown:    ${max_dd:.2f}")
    print()


def show_by_grade(conn):
    sep()
    print("  WIN RATE BY SETUP GRADE")
    sep()
    for grade in ["A", "B", "C"]:
        rows = conn.execute(
            "SELECT pnl_usd, pnl_r FROM trades WHERE status='closed' AND setup_grade=?",
            (grade,)
        ).fetchall()
        if not rows:
            print(f"  Grade {grade}:  No trades yet")
            continue
        wins     = [r for r in rows if r["pnl_usd"] > 0]
        win_rate = len(wins) / len(rows) * 100
        net_pnl  = sum(r["pnl_usd"] for r in rows)
        avg_r    = sum(r["pnl_r"] for r in rows) / len(rows)
        print(
            f"  Grade {grade}:  {len(rows):>3} trades  "
            f"WR={win_rate:.0f}%  {bar(win_rate, 12)}  "
            f"Net={pnl_color(net_pnl)}  AvgR={avg_r:+.2f}"
        )
    print()


def show_by_regime(conn):
    sep()
    print("  WIN RATE BY REGIME")
    sep()
    regimes = conn.execute(
        "SELECT DISTINCT regime FROM trades WHERE status='closed' AND regime IS NOT NULL"
    ).fetchall()
    if not regimes:
        print("  No closed trades yet.")
        print()
        return
    for reg in regimes:
        r_name = reg["regime"]
        rows = conn.execute(
            "SELECT pnl_usd, pnl_r FROM trades WHERE status='closed' AND regime=?",
            (r_name,)
        ).fetchall()
        wins     = [r for r in rows if r["pnl_usd"] > 0]
        win_rate = len(wins) / len(rows) * 100 if rows else 0
        net_pnl  = sum(r["pnl_usd"] for r in rows)
        avg_r    = sum(r["pnl_r"] for r in rows) / len(rows) if rows else 0
        print(
            f"  {r_name:<22} {len(rows):>3} trades  "
            f"WR={win_rate:.0f}%  Net={pnl_color(net_pnl)}  AvgR={avg_r:+.2f}"
        )
    print()


def show_recent(conn, n=10):
    rows = conn.execute(
        "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT ?", (n,)
    ).fetchall()
    sep()
    print(f"  LAST {n} CLOSED TRADES")
    sep()
    if not rows:
        print("  No closed trades yet.")
        print()
        return
    print(f"  {'ID':<10} {'Dir':<6} {'Grade':<6} {'P&L':>10} {'R':>6}  {'Exit (ET)':<18}  Reason")
    sep()
    for r in rows:
        print(
            f"  {r['trade_id'][:8]:<10} "
            f"{r['direction'].upper():<6} "
            f"{r['setup_grade'] or '?':<6} "
            f"{pnl_color(r['pnl_usd']):>10} "
            f"{r['pnl_r']:>+5.2f}R  "
            f"{to_et(r['exit_time']):<18}  "
            f"{r['exit_reason'] or ''}"
        )
    print()


def show_circuit_breakers(conn):
    rows = conn.execute(
        "SELECT * FROM circuit_breaker_log ORDER BY triggered_at DESC LIMIT 5"
    ).fetchall()
    if not rows:
        return
    sep()
    print("  RECENT CIRCUIT BREAKERS")
    sep()
    for r in rows:
        print(f"  {to_et(r['triggered_at'])}  {r['reason']}  loss=${r['daily_loss']:.2f}")
    print()


def main():
    conn = connect()
    print()
    sep("═")
    print(f"  {INSTRUMENT} ADAPTIVE TRADING BOT — PERFORMANCE DASHBOARD")
    print(f"  {now_et().strftime('%Y-%m-%d %H:%M:%S ET')}")
    sep("═")
    print()
    show_open_position(conn)
    show_today(conn)
    show_alltime(conn)
    show_by_grade(conn)
    show_by_regime(conn)
    show_recent(conn)
    show_circuit_breakers(conn)
    sep("═")
    print()
    conn.close()


if __name__ == "__main__":
    main()
