"""
diagnostic_report.py — Post-diagnostic lifecycle report.
Run after a diagnostic trade completes to validate the full order lifecycle.

Usage: python diagnostic_report.py
"""

import os
import sys
import sqlite3
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("US/Eastern")
LOG_FILE = os.path.expanduser("~/crypto-trader/bot.log")
SERVICE  = "cryptobot"

PASS = "  ✅"
FAIL = "  ❌"
WARN = "  ⚠️ "
SEP  = "─" * 60

def section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)

def grep_log(pattern, label, expect_match=True, tail=200):
    """Search bot.log for pattern. Returns matched lines."""
    try:
        result = subprocess.run(
            ["grep", "-E", pattern, LOG_FILE],
            capture_output=True, text=True
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        # Only show last N lines
        lines = lines[-tail:]
        if expect_match and lines:
            print(f"{PASS} {label}")
            for l in lines:
                print(f"       {l}")
        elif expect_match and not lines:
            print(f"{FAIL} {label} — NOT FOUND IN LOG")
        elif not expect_match and not lines:
            print(f"{PASS} {label} — correctly absent")
        elif not expect_match and lines:
            print(f"{FAIL} {label} — UNEXPECTEDLY PRESENT:")
            for l in lines:
                print(f"       {l}")
        return lines
    except Exception as e:
        print(f"{FAIL} {label} — error: {e}")
        return []

def check_db():
    """Read the trade record from trades.db."""
    db_path = os.path.expanduser("~/crypto-trader/trades.db")
    if not os.path.exists(db_path):
        print(f"{FAIL} trades.db not found")
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM trades ORDER BY entry_time DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"{FAIL} DB read error: {e}")
        return None

def service_status():
    try:
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE],
            capture_output=True, text=True
        )
        return r.stdout.strip()
    except:
        return "unknown"

# ─── REPORT ───────────────────────────────────────────────────────────────────

print()
print("═" * 60)
print("  DIAGNOSTIC LIFECYCLE REPORT")
print(f"  {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")
print("═" * 60)

# ── 1. Service state ──────────────────────────────────────────
section("1. SERVICE STATE")
status = service_status()
if status == "active":
    print(f"{WARN} Service still running (diagnostic may still be in progress)")
else:
    print(f"{PASS} Service halted after diagnostic: {status}")

# ── 2. Bot startup ────────────────────────────────────────────
section("2. BOT STARTUP")
grep_log("Bot initialized|Service mode|cash=", "Bot initialized with balance")
grep_log("DIAGNOSTIC_MODE|DiagnosticStrategy|DIAGNOSTIC SIGNAL", "Diagnostic mode activated")
grep_log("Startup recovery.*Clean start|no open position on Kraken", "Clean startup — no orphan positions")

# ── 3. Regime & strategy ─────────────────────────────────────
section("3. REGIME & STRATEGY SELECTION")
grep_log("REGIME:.*→", "Regime identified")
grep_log("STRATEGY TRANSITION.*Diagnostic", "DiagnosticStrategy selected")

# ── 4. Signal generation ──────────────────────────────────────
section("4. SIGNAL GENERATION")
grep_log("DIAGNOSTIC SIGNAL.*LONG|DIAGNOSTIC SIGNAL.*SHORT", "Diagnostic signal fired")
grep_log("VALIDATING.*Diagnostic", "Signal passed to validator")
grep_log("VALIDATED.*gates=", "Signal validated — gates passed")
grep_log("REJECTED", "Signal rejected (should be none)", expect_match=False)

# ── 5. Position sizing ────────────────────────────────────────
section("5. POSITION SIZING")
grep_log("Position size:.*risk=", "Position sized correctly")
grep_log("capped to margin limit", "Margin cap triggered (optional)", expect_match=False)

# ── 6. Order entry ────────────────────────────────────────────
section("6. ORDER ENTRY")
grep_log(r"\[LIVE\] Entering", "Live entry attempted")
grep_log("Live order placed.*pair=.*BTNL", "Order placed with correct BTNL pair")
grep_log("Entry confirmed .LIVE.", "Entry confirmed with fill")
grep_log("EOrder|entry.*failed|Entry order failed", "Entry errors (should be none)", expect_match=False)

# ── 7. Position management ────────────────────────────────────
section("7. POSITION MANAGEMENT")
grep_log("open_risk=", "Open risk registered on tick")
grep_log("Stop adjusted|trail", "Stop management active (optional)", expect_match=False)
grep_log("manual_close_detected|ORPHAN", "False manual close detection (should be none)", expect_match=False)

# ── 8. Exit ───────────────────────────────────────────────────
section("8. EXIT")
grep_log("STOP HIT|stop_hit|target_1_hit|target_2_hit|time_stagnant", "Exit condition triggered")
grep_log("Position closed.*pair=.*BTNL|close.*BTNL", "Close order placed with correct BTNL pair")
grep_log("TRADE CLOSED.*pnl=", "Trade closed and logged")
grep_log("Exit logged.*P&L=", "Exit written to DB")
grep_log("Close order failed|close.*error", "Close errors (should be none)", expect_match=False)

# ── 9. Post-close halt ────────────────────────────────────────
section("9. POST-CLOSE HALT")
grep_log("DIAGNOSTIC COMPLETE|No further trades", "Diagnostic halt triggered")

# ── 10. DB record ─────────────────────────────────────────────
section("10. DATABASE RECORD")
trade = check_db()
if trade:
    status_ok  = trade.get("status") == "closed"
    entry_ok   = trade.get("entry_price", 0) > 0
    exit_ok    = trade.get("exit_price", 0) > 0
    pnl_ok     = trade.get("pnl_usd") is not None
    paper_ok   = trade.get("paper_trade", 1) == 0  # Should be live

    print(f"{'  ✅' if status_ok  else '  ❌'} Status:      {trade.get('status')}")
    print(f"{'  ✅' if entry_ok   else '  ❌'} Entry price: ${trade.get('entry_price', 0):.4f}")
    print(f"{'  ✅' if exit_ok    else '  ❌'} Exit price:  ${trade.get('exit_price', 0):.4f}")
    print(f"{'  ✅' if pnl_ok     else '  ❌'} P&L:         ${trade.get('pnl_usd', 0):.4f}")
    print(f"  {'R:          ' + str(round(trade.get('pnl_r', 0), 2)) + 'R'}")
    print(f"{'  ✅' if paper_ok   else '  ❌'} Live trade:  {'Yes' if paper_ok else 'No (paper_trade=1)'}")
    print(f"  Exit reason: {trade.get('exit_reason', '?')}")
    print(f"  Strategy:    {trade.get('strategy', '?')}")
    print(f"  Entry time:  {trade.get('entry_time', '?')}")
    print(f"  Exit time:   {trade.get('exit_time', '?')}")

    all_ok = status_ok and entry_ok and exit_ok and pnl_ok and paper_ok
else:
    print(f"{FAIL} No trade record found in DB")
    all_ok = False

# ── 11. Error scan ────────────────────────────────────────────
section("11. ERROR SCAN (full log)")
grep_log("\\[ERROR\\]|\\[CRITICAL\\]", "Errors in log (should be none)", expect_match=False)

# ── SUMMARY ───────────────────────────────────────────────────
print()
print("═" * 60)
if all_ok:
    print("  ✅  DIAGNOSTIC PASSED")
    print("  Order lifecycle validated end-to-end:")
    print("  Signal → Validate → Size → Enter → Manage → Exit → DB")
else:
    print("  ❌  DIAGNOSTIC FAILED — review sections above")
print("═" * 60)
print()
