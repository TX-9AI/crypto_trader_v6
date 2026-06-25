"""
report.py — Trading Performance Report Generator
Reads trades.db and generates a self-contained HTML report.

Usage:
    python report.py              # generates report.html in current directory
    python report.py --out /path  # custom output path
    python report.py --live       # live trades only
    python report.py --paper      # paper trades only
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("US/Eastern")

INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, INSTALL_DIR)

try:
    from config import DB_PATH, TRADING_SYMBOL
except Exception:
    DB_PATH        = os.path.expanduser("~/crypto-trader/trades.db")
    TRADING_SYMBOL = "BTC/USD"

# ── Helpers ───────────────────────────────────────────────────────────────────

def to_et(ts):
    if not ts: return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts[:16]

def session_of(ts):
    """Classify trade entry into Asia / London / NY session."""
    if not ts: return "Unknown"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        et = dt.astimezone(ET)
        h  = et.hour + et.minute / 60
        if 20 <= h or h < 3:   return "Asia Open"
        if 3  <= h < 8:        return "Asia Late"
        if 8  <= h < 9.5:      return "Pre-Market"
        if 9.5 <= h < 12:      return "NY Morning"
        if 12 <= h < 14:       return "NY Midday"
        if 14 <= h < 16:       return "NY Afternoon"
        return "After Hours"
    except Exception:
        return "Unknown"

def duration_min(entry_ts, exit_ts):
    if not entry_ts or not exit_ts: return None
    try:
        def parse(ts):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        return round((parse(exit_ts) - parse(entry_ts)).total_seconds() / 60, 1)
    except Exception:
        return None

def pct_color(val):
    if val is None: return "#888"
    return "#00c97a" if val >= 0 else "#ff4d6d"

def r_badge(r):
    if r is None: return "—"
    color = "#00c97a" if r >= 0 else "#ff4d6d"
    return f'<span style="color:{color};font-weight:600">{r:+.2f}R</span>'

def pnl_cell(val):
    if val is None: return "—"
    color = "#00c97a" if val >= 0 else "#ff4d6d"
    sign  = "+" if val >= 0 else ""
    return f'<span style="color:{color}">{sign}${val:,.2f}</span>'

def grade_badge(g):
    colors = {"A": "#f5a623", "B": "#4a90e2", "C": "#888"}
    c = colors.get(g, "#888")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{g}</span>'

def stat_box(label, value, sub=""):
    return f'''
    <div class="stat-box">
        <div class="stat-label">{label}</div>
        <div class="stat-value">{value}</div>
        {"<div class='stat-sub'>" + sub + "</div>" if sub else ""}
    </div>'''

def mini_bar(pct, color="#00c97a", width=120):
    fill = max(0, min(100, pct * 100))
    return f'''<div style="background:#2a2a3a;border-radius:4px;width:{width}px;height:8px;display:inline-block;vertical-align:middle">
        <div style="background:{color};width:{fill}%px;height:8px;border-radius:4px;transition:width 0.3s"></div></div>'''

# ── Data loading ──────────────────────────────────────────────────────────────

def load_trades(mode_filter=None):
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM trades WHERE status='closed' AND pnl_usd IS NOT NULL"
    if mode_filter == "live":  q += " AND paper_trade=0"
    if mode_filter == "paper": q += " AND paper_trade=1"
    q += " ORDER BY entry_time ASC"
    rows = [dict(r) for r in conn.execute(q).fetchall()]
    conn.close()
    # Enrich
    for t in rows:
        t["session"]  = session_of(t.get("entry_time"))
        t["duration"] = duration_min(t.get("entry_time"), t.get("exit_time"))
        t["et_entry"] = to_et(t.get("entry_time"))
        t["et_exit"]  = to_et(t.get("exit_time"))
    return rows

def load_open():
    if not os.path.exists(DB_PATH): return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM trades WHERE status='open' LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

# ── Analytics ─────────────────────────────────────────────────────────────────

def compute_stats(trades):
    if not trades:
        return {}
    pnls   = [t["pnl_usd"] for t in trades if t["pnl_usd"] is not None]
    rs     = [t["pnl_r"]   for t in trades if t["pnl_r"]   is not None]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    net    = sum(pnls)
    wr     = len(wins) / len(pnls) if pnls else 0
    avg_w  = sum(wins)   / len(wins)   if wins   else 0
    avg_l  = sum(losses) / len(losses) if losses else 0
    pf     = abs(sum(wins) / sum(losses)) if losses else float("inf")
    avg_r  = sum(rs) / len(rs) if rs else 0

    # Max drawdown
    equity = 0
    peak   = 0
    max_dd = 0
    for p in pnls:
        equity += p
        if equity > peak: peak = equity
        dd = peak - equity
        if dd > max_dd: max_dd = dd

    # Rolling PnL for chart
    rolling = []
    cum     = 0
    for t in trades:
        cum += t["pnl_usd"] or 0
        rolling.append({"time": t["et_entry"], "pnl": round(cum, 2)})

    # By session
    by_session = {}
    for t in trades:
        s = t["session"]
        if s not in by_session:
            by_session[s] = {"trades": 0, "wins": 0, "pnl": 0}
        by_session[s]["trades"] += 1
        if (t["pnl_usd"] or 0) > 0:
            by_session[s]["wins"] += 1
        by_session[s]["pnl"] += t["pnl_usd"] or 0

    # By strategy
    by_strategy = {}
    for t in trades:
        s = t.get("strategy") or "Unknown"
        if s not in by_strategy:
            by_strategy[s] = {"trades": 0, "wins": 0, "pnl": 0, "r": []}
        by_strategy[s]["trades"] += 1
        if (t["pnl_usd"] or 0) > 0:
            by_strategy[s]["wins"] += 1
        by_strategy[s]["pnl"] += t["pnl_usd"] or 0
        if t["pnl_r"]: by_strategy[s]["r"].append(t["pnl_r"])

    # By regime
    by_regime = {}
    for t in trades:
        r = t.get("regime") or "Unknown"
        if r not in by_regime:
            by_regime[r] = {"trades": 0, "wins": 0, "pnl": 0}
        by_regime[r]["trades"] += 1
        if (t["pnl_usd"] or 0) > 0:
            by_regime[r]["wins"] += 1
        by_regime[r]["pnl"] += t["pnl_usd"] or 0

    # By grade
    by_grade = {}
    for t in trades:
        g = t.get("setup_grade") or "?"
        if g not in by_grade:
            by_grade[g] = {"trades": 0, "wins": 0, "pnl": 0, "r": []}
        by_grade[g]["trades"] += 1
        if (t["pnl_usd"] or 0) > 0:
            by_grade[g]["wins"] += 1
        by_grade[g]["pnl"] += t["pnl_usd"] or 0
        if t["pnl_r"]: by_grade[g]["r"].append(t["pnl_r"])

    # By day of week
    by_dow = {d: {"trades":0,"wins":0,"pnl":0} for d in
              ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}
    for t in trades:
        try:
            dt  = datetime.fromisoformat((t["entry_time"] or "").replace("Z","+00:00"))
            dow = dt.astimezone(ET).strftime("%A")
            by_dow[dow]["trades"] += 1
            if (t["pnl_usd"] or 0) > 0:
                by_dow[dow]["wins"] += 1
            by_dow[dow]["pnl"] += t["pnl_usd"] or 0
        except Exception:
            pass

    # Streak analysis
    streak_cur = 0; streak_max_w = 0; streak_max_l = 0; streak_type = None
    for p in pnls:
        win = p > 0
        if streak_type is None:
            streak_type = win; streak_cur = 1
        elif win == streak_type:
            streak_cur += 1
        else:
            if streak_type:     streak_max_w = max(streak_max_w, streak_cur)
            else:               streak_max_l = max(streak_max_l, streak_cur)
            streak_type = win; streak_cur = 1
    if streak_type is True:  streak_max_w = max(streak_max_w, streak_cur)
    if streak_type is False: streak_max_l = max(streak_max_l, streak_cur)

    # Avg duration
    durs = [t["duration"] for t in trades if t["duration"] is not None]
    avg_dur = sum(durs) / len(durs) if durs else 0

    # Best/worst
    best  = max(trades, key=lambda t: t["pnl_usd"] or 0)
    worst = min(trades, key=lambda t: t["pnl_usd"] or 0)

    return dict(
        total=len(pnls), wins=len(wins), losses=len(losses),
        net=net, wr=wr, avg_w=avg_w, avg_l=avg_l, pf=pf,
        avg_r=avg_r, max_dd=max_dd, rolling=rolling,
        by_session=by_session, by_strategy=by_strategy,
        by_regime=by_regime, by_grade=by_grade, by_dow=by_dow,
        streak_max_w=streak_max_w, streak_max_l=streak_max_l,
        avg_dur=avg_dur, best=best, worst=worst,
    )

# ── HTML generation ───────────────────────────────────────────────────────────

def build_html(trades, stats, mode_filter, open_trade):
    now_et   = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    mode_lbl = {"live": "LIVE", "paper": "PAPER", None: "ALL"}.get(mode_filter, "ALL")
    instr    = TRADING_SYMBOL

    if not stats:
        body = '<div style="text-align:center;padding:80px;color:#888;font-size:18px">No closed trades found.</div>'
    else:
        # ── Rolling PnL chart data ─────────────────────────────────────────
        chart_labels = [r["time"] for r in stats["rolling"]]
        chart_data   = [r["pnl"]  for r in stats["rolling"]]
        chart_colors = ["#00c97a" if v >= 0 else "#ff4d6d" for v in chart_data]

        # ── Summary stats ──────────────────────────────────────────────────
        pf_str = f"{stats['pf']:.2f}" if stats['pf'] != float('inf') else "∞"
        summary = f'''
        <div class="stats-grid">
            {stat_box("Net P&L", f'<span style="color:{pct_color(stats["net"])}">${stats["net"]:+,.2f}</span>')}
            {stat_box("Win Rate", f'{stats["wr"]*100:.1f}%', f'{stats["wins"]}W / {stats["losses"]}L / {stats["total"]} trades')}
            {stat_box("Avg R/Trade", f'<span style="color:{pct_color(stats["avg_r"])}">{stats["avg_r"]:+.2f}R</span>')}
            {stat_box("Profit Factor", pf_str)}
            {stat_box("Avg Win", f'<span style="color:#00c97a">${stats["avg_w"]:,.2f}</span>')}
            {stat_box("Avg Loss", f'<span style="color:#ff4d6d">${abs(stats["avg_l"]):,.2f}</span>')}
            {stat_box("Max Drawdown", f'<span style="color:#ff4d6d">${stats["max_dd"]:,.2f}</span>')}
            {stat_box("Avg Duration", f'{stats["avg_dur"]:.0f} min')}
            {stat_box("Best Trade", f'<span style="color:#00c97a">${stats["best"]["pnl_usd"]:+,.2f}</span>', stats["best"]["et_entry"])}
            {stat_box("Worst Trade", f'<span style="color:#ff4d6d">${stats["worst"]["pnl_usd"]:+,.2f}</span>', stats["worst"]["et_entry"])}
            {stat_box("Max Win Streak", str(stats["streak_max_w"]))}
            {stat_box("Max Loss Streak", str(stats["streak_max_l"]))}
        </div>'''

        # ── Rolling PnL chart ──────────────────────────────────────────────
        chart = f'''
        <div class="card">
            <h2>📈 Rolling P&L</h2>
            <canvas id="pnlChart" height="80"></canvas>
        </div>
        <script>
        new Chart(document.getElementById('pnlChart'), {{
            type: 'line',
            data: {{
                labels: {chart_labels},
                datasets: [{{
                    label: 'Cumulative P&L',
                    data: {chart_data},
                    borderColor: '#00c97a',
                    backgroundColor: 'rgba(0,201,122,0.08)',
                    pointBackgroundColor: {chart_colors},
                    pointRadius: 4,
                    fill: true,
                    tension: 0.3
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }},
                    tooltip: {{ callbacks: {{ label: ctx => '$' + ctx.parsed.y.toFixed(2) }} }} }},
                scales: {{
                    x: {{ ticks: {{ color:'#888', maxTicksLimit:10 }}, grid:{{ color:'#2a2a3a' }} }},
                    y: {{ ticks: {{ color:'#888', callback: v => '$'+v }}, grid:{{ color:'#2a2a3a' }} }}
                }}
            }}
        }});
        </script>'''

        # ── Breakdown tables ───────────────────────────────────────────────
        def breakdown_table(title, data, sort_key="pnl"):
            if not data: return ""
            rows_html = ""
            for k, v in sorted(data.items(), key=lambda x: -abs(x[1].get(sort_key,0))):
                t  = v["trades"]
                w  = v["wins"]
                wr = w/t*100 if t else 0
                p  = v["pnl"]
                ar = sum(v["r"])/len(v["r"]) if v.get("r") else None
                wr_bar = f'<div style="background:#2a2a3a;border-radius:3px;height:6px;width:80px;display:inline-block;vertical-align:middle;margin-left:8px"><div style="background:#00c97a;width:{min(100,wr):.0f}%;height:6px;border-radius:3px"></div></div>'
                ar_str = f'{ar:+.2f}R' if ar is not None else '—'
                ar_col = pct_color(ar) if ar is not None else '#888'
                rows_html += f'''<tr>
                    <td>{k}</td>
                    <td>{t}</td>
                    <td>{wr:.0f}% {wr_bar}</td>
                    <td>{pnl_cell(p)}</td>
                    <td><span style="color:{ar_col}">{ar_str}</span></td>
                </tr>'''
            return f'''<div class="card"><h2>{title}</h2>
            <table><thead><tr><th>Name</th><th>Trades</th><th>Win Rate</th><th>P&L</th><th>Avg R</th></tr></thead>
            <tbody>{rows_html}</tbody></table></div>'''

        breakdowns = (
            breakdown_table("⏰ Performance by Session",  stats["by_session"])  +
            breakdown_table("🎯 Performance by Strategy", stats["by_strategy"]) +
            breakdown_table("📊 Performance by Regime",   stats["by_regime"])   +
            breakdown_table("🏅 Performance by Grade",    stats["by_grade"])    +
            breakdown_table("📅 Performance by Day",      stats["by_dow"])
        )

        # ── Trade log ─────────────────────────────────────────────────────
        trade_rows = ""
        for t in reversed(trades):
            dur   = f'{t["duration"]:.0f}m' if t["duration"] else "—"
            mode  = "LIVE" if not t.get("paper_trade") else "paper"
            mcol  = "#ff4d6d" if mode == "LIVE" else "#888"
            trade_rows += f'''<tr>
                <td style="font-family:monospace;font-size:11px">{(t.get("trade_id") or "")[:8]}</td>
                <td>{t.get("et_entry","—")}</td>
                <td>{"🟢 LONG" if t.get("direction")=="long" else "🔴 SHORT"}</td>
                <td>{grade_badge(t.get("setup_grade","?"))}</td>
                <td>{t.get("strategy","—")}</td>
                <td>{t.get("regime","—")}</td>
                <td>{t.get("session","—")}</td>
                <td>${t.get("entry_price",0):,.2f}</td>
                <td>${t.get("exit_price",0):,.2f}</td>
                <td>${t.get("risk_usd",0):,.2f}</td>
                <td>{pnl_cell(t.get("pnl_usd"))}</td>
                <td>{r_badge(t.get("pnl_r"))}</td>
                <td>{dur}</td>
                <td style="font-size:11px;color:#888">{t.get("exit_reason","—")}</td>
                <td><span style="color:{mcol};font-size:11px">{mode}</span></td>
            </tr>'''

        trade_log = f'''<div class="card">
            <h2>📋 Trade Log</h2>
            <div style="overflow-x:auto">
            <table><thead><tr>
                <th>ID</th><th>Entry (ET)</th><th>Dir</th><th>Grade</th>
                <th>Strategy</th><th>Regime</th><th>Session</th>
                <th>Entry $</th><th>Exit $</th><th>Risk $</th>
                <th>P&L</th><th>R</th><th>Duration</th><th>Exit Reason</th><th>Mode</th>
            </tr></thead><tbody>{trade_rows}</tbody></table>
            </div></div>'''

        # ── Open position ─────────────────────────────────────────────────
        open_html = ""
        if open_trade:
            d  = open_trade.get("direction","").upper()
            ep = open_trade.get("entry_price", 0)
            sp = open_trade.get("stop_price",  0)
            t1 = open_trade.get("target_1",    0)
            gr = open_trade.get("setup_grade", "?")
            st = open_trade.get("strategy",    "—")
            re = open_trade.get("regime",      "—")
            et = to_et(open_trade.get("entry_time"))
            open_html = f'''<div class="card" style="border-left:3px solid #f5a623">
                <h2>⚡ Open Position</h2>
                <div class="stats-grid">
                    {stat_box("Direction", d)}
                    {stat_box("Strategy", st)}
                    {stat_box("Grade", grade_badge(gr))}
                    {stat_box("Regime", re)}
                    {stat_box("Entry", f"${ep:,.2f}")}
                    {stat_box("Stop", f"${sp:,.2f}")}
                    {stat_box("Target", f"${t1:,.2f}")}
                    {stat_box("Entered", et)}
                </div></div>'''

        body = summary + chart + open_html + breakdowns + trade_log

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vertigo Capital — Trading Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0d0d1a; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; line-height: 1.5; }}
    .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 32px 40px; border-bottom: 1px solid #2a2a3a; }}
    .header h1 {{ font-size: 26px; font-weight: 700; color: #00c97a; letter-spacing: -0.5px; }}
    .header .meta {{ color: #888; font-size: 13px; margin-top: 6px; }}
    .mode-badge {{ display:inline-block; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:700; margin-left:10px;
        background: {"#ff4d6d" if mode_lbl=="LIVE" else "#4a90e2" if mode_lbl=="PAPER" else "#555"}; color:#fff; }}
    .container {{ max-width: 1400px; margin: 0 auto; padding: 24px 20px; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .stat-box {{ background: #1a1a2e; border: 1px solid #2a2a3a; border-radius: 10px; padding: 16px; }}
    .stat-label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
    .stat-value {{ font-size: 20px; font-weight: 700; }}
    .stat-sub {{ font-size: 11px; color: #888; margin-top: 4px; }}
    .card {{ background: #1a1a2e; border: 1px solid #2a2a3a; border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
    .card h2 {{ font-size: 15px; font-weight: 600; margin-bottom: 18px; color: #ccc; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    thead tr {{ border-bottom: 1px solid #2a2a3a; }}
    th {{ text-align: left; padding: 8px 12px; color: #888; font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #1e1e2e; white-space: nowrap; }}
    tr:hover td {{ background: #1e1e2e; }}
    tr:last-child td {{ border-bottom: none; }}
    @media (max-width: 600px) {{ .container {{ padding: 12px; }} .stats-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
<div class="header">
    <h1>Vertigo Capital <span class="mode-badge">{mode_lbl}</span></h1>
    <div class="meta">{instr} · Generated {now_et}</div>
</div>
<div class="container">
{body}
</div>
</body>
</html>'''
    return html

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate trading performance report")
    parser.add_argument("--out",   default="report.html", help="Output file path")
    parser.add_argument("--live",  action="store_true",   help="Live trades only")
    parser.add_argument("--paper", action="store_true",   help="Paper trades only")
    args = parser.parse_args()

    mode = "live" if args.live else "paper" if args.paper else None

    print(f"Loading trades from {DB_PATH}...")
    trades     = load_trades(mode)
    open_trade = load_open()
    stats      = compute_stats(trades)

    print(f"  {len(trades)} closed trades found")
    if stats:
        print(f"  Net P&L:  ${stats['net']:+,.2f}")
        print(f"  Win rate: {stats['wr']*100:.1f}%")

    html = build_html(trades, stats, mode, open_trade)

    out_path = args.out
    with open(out_path, "w") as f:
        f.write(html)

    print(f"\n✅ Report saved: {out_path}")
    print(f"   Open in browser: file://{os.path.abspath(out_path)}")

if __name__ == "__main__":
    main()
