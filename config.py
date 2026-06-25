"""
config.py — crypto_trader v6.0
================================
BTC/USD only. Fee-aware. Auto-sizing based on grade and live balance.
No user-configured position sizes. No circuit breaker.

Key changes from v5.0:
  - BTC/USD only (XBT/USD:BTNL on Kraken margin)
  - Fee constants baked in — all entry decisions account for fees
  - Position size auto-calculated from grade × account balance × leverage
  - Circuit breaker removed — fee floor gate does the job
  - Daily range filter on SweepReversal / MeanReversion
  - Paper trading uses full 10× margin of configured cash balance
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from credentials import (
    KRAKEN_API_KEY,
    KRAKEN_API_SECRET,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
    ALERT_TO_PHONE,
    BOT_NAME,
)

# ─── INSTRUMENT — BTC ONLY ────────────────────────────────────────────────────
TRADING_SYMBOL  = "BTC/USD"
KRAKEN_SYMBOL   = "XBT/USD:BTNL"
INSTRUMENT      = "BTC"

# ─── ACCOUNT ──────────────────────────────────────────────────────────────────
ACCOUNT_BALANCE_USD       = float(os.environ.get("BOT_CASH_BALANCE", "1750"))
LEVERAGE                  = 10
# Buying power = ACCOUNT_BALANCE_USD × LEVERAGE
# e.g. $1750 cash × 10x = $17,500 buying power

# ─── MODE ─────────────────────────────────────────────────────────────────────
PAPER_TRADING             = os.environ.get("PAPER_TRADING", "True") != "False"

# ─── AUTO POSITION SIZING — grade-based notional pct of buying power ──────────
# Position size = (cash × leverage × notional_pct) / entry_price
# A grade: 90% of buying power  → aggressive, high-conviction only
# B grade: 75% of buying power  → standard setups
# C grade: 50% of buying power  → reduced, lower conviction
GRADE_A_NOTIONAL_PCT      = 0.90
GRADE_B_NOTIONAL_PCT      = 0.75
GRADE_C_NOTIONAL_PCT      = 0.50
TRADE_GRADE_C             = False   # C grades disabled by default

# ─── KRAKEN FEE STRUCTURE ─────────────────────────────────────────────────────
# Market orders = taker rate. Base tier (< $2,500/month volume).
# Update these when your 30-day volume moves to a higher tier.
KRAKEN_TAKER_FEE          = 0.0080  # 0.80% per side (base tier taker)
KRAKEN_MAKER_FEE          = 0.0040  # 0.40% per side (base tier maker, FYI only)

# Margin-specific fees — charged on notional at open and every 4 hours
# BTC margin: 0.01%-0.02% open, 0.01%-0.02% rollover. Using conservative 0.02%.
KRAKEN_MARGIN_OPEN_FEE    = 0.0002  # 0.02% of notional at open
KRAKEN_ROLLOVER_FEE       = 0.0002  # 0.02% of notional per 4-hour window
KRAKEN_ROLLOVER_HOURS     = 4       # Hours per rollover interval

# Minimum fee-adjusted 1R profit required to take a trade
# Trade is rejected if projected 1R profit <= round-trip fees
# Set to 1.0 = must clear fees exactly. 1.3 = 30% above fees.
MIN_FEE_ADJUSTED_R        = 1.0

# ─── DAILY RANGE FILTER ───────────────────────────────────────────────────────
# BTC must show minimum daily range before SweepReversal / MeanReversion fire.
# Prevents trading in dead compression where fees eat all profit.
# 0.008 = 0.8% of price (~$490 on $61k BTC). Adjust based on observation.
MIN_DAILY_RANGE_PCT       = 0.008

# ─── ENTRY GATES ──────────────────────────────────────────────────────────────
MIN_RRR                   = 1.5
VWAP_FILTER_ACTIVE        = True
MIN_TF_CONFLUENCE         = 1
ENTRY_COOLDOWN_MINUTES    = 5

# ─── SETUP SCORER ─────────────────────────────────────────────────────────────
GRADE_A_MIN_SCORE         = 0.78
GRADE_B_MIN_SCORE         = 0.55
GRADE_SIZE_MULTIPLIER     = {"A": 1.0, "B": 1.0, "C": 0.5}  # Handled by notional pct now

# ─── STOPS ────────────────────────────────────────────────────────────────────
ATR_STOP_MULTIPLIER       = 1.5

# ─── REGIME ───────────────────────────────────────────────────────────────────
ADX_TREND_THRESHOLD       = 20
ADX_RANGE_THRESHOLD       = 15
ATR_EXPANSION_MULTIPLIER  = 1.5
BB_WIDTH_COMPRESSION_PCT  = 0.20
SWEEP_REJECTION_CANDLES   = 2
EQUAL_LEVEL_PCT           = 0.001
REGIME_REASSESS_MINUTES   = 5

# ─── VIX ──────────────────────────────────────────────────────────────────────
VIX_LOW_THRESHOLD         = 15
VIX_ELEVATED_THRESHOLD    = 25
VIX_CRISIS_THRESHOLD      = 35
VIX_CRISIS_NO_LONG        = True
VIX_NO_ENTRY_THRESHOLD    = 30

# ─── STRATEGY PARAMETERS ──────────────────────────────────────────────────────
BB_PERIOD                 = 20
BB_STD                    = 2.0
EMA_FAST                  = 9
EMA_MID                   = 21
EMA_SLOW                  = 50
EMA_ANCHOR                = 200
ATR_PERIOD                = 14

# ─── LIQUIDITY ────────────────────────────────────────────────────────────────
EQUAL_HIGH_LOW_LOOKBACK   = 50
ORDER_BLOCK_LOOKBACK      = 20
IMBALANCE_MIN_SIZE_PCT    = 0.002
LIQUIDITY_BUFFER_PCT      = 0.003

# ─── STRUCTURE ────────────────────────────────────────────────────────────────
SWING_LOOKBACK            = 10
MIN_SWING_SIZE_ATR        = 0.5
FVG_MIN_SIZE_PCT          = 0.001
SR_TOUCH_MIN              = 2
SR_ZONE_PCT               = 0.002

# ─── EXIT / TRAIL ─────────────────────────────────────────────────────────────
TRAIL_ACTIVATION_R        = 1.0
TRAIL_STEP_1_R            = 1.0
TRAIL_STEP_2_R            = 2.0
TRAIL_STEP_3_R            = 3.0
TRAIL_TIGHTEN_ON_REGIME   = 0.25
PARTIAL_EXIT_PCT          = 0.50
PARTIAL_MINIMUM_R         = 0.75
STAGNANT_TRADE_MINUTES    = 120

# ─── ORDER EXECUTION ──────────────────────────────────────────────────────────
ORDER_TYPE_DEFAULT        = "market"
LIMIT_ORDER_SLIPPAGE_PCT  = 0.0005
PAPER_FILL_SLIPPAGE_PCT   = 0.001
POLL_INTERVAL_SECONDS     = 10

# ─── TIMEFRAMES ───────────────────────────────────────────────────────────────
TIMEFRAMES = {
    "1d":  {"candles": 10,  "role": "bias"},
    "1h":  {"candles": 50,  "role": "structure"},
    "15m": {"candles": 50,  "role": "trend"},
    "5m":  {"candles": 100, "role": "entry_context"},
    "1m":  {"candles": 60,  "role": "trigger"},
}
CACHE_STALENESS_SECONDS = {
    "1d": 3600, "1h": 300, "15m": 120, "5m": 30, "1m": 10,
}

# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
NOTIFY_ON_ENTRY           = True
NOTIFY_ON_EXIT            = True
NOTIFY_CIRCUIT_BREAKER    = False   # No circuit breaker in v6
NOTIFY_REGIME_CHANGE      = False
NOTIFY_ON_REGIME_CHANGE   = True
NOTIFY_PNL_UPDATE_MINUTES = 30
NOTIFY_CONSECUTIVE_LOSS   = True

# ─── MAX OPEN RISK ────────────────────────────────────────────────────────────
MAX_OPEN_RISK_PCT         = 1.0  # Only one position at a time on BTC

# ─── PATHS ────────────────────────────────────────────────────────────────────
DB_PATH                   = os.path.expanduser("~/crypto-trader/trades.db")
LOG_FILE                  = os.path.expanduser("~/crypto-trader/bot.log")
LOG_ROTATION_MB           = 50
LOG_LEVEL                 = "INFO"

# ─── MACRO ────────────────────────────────────────────────────────────────────
FOREX_FACTORY_URL         = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
MACRO_FETCH_INTERVAL_MIN  = 60

# ─── MISC ─────────────────────────────────────────────────────────────────────
TRADING_24_7              = True
BLACKOUT_WINDOWS          = []
MAX_CONSECUTIVE_LOSSES    = 3   # Used for Telegram alerts only, not blocking
MIN_ORDER_SIZE_BTC        = 0.0001
DIAGNOSTIC_MODE           = False

SCORE_WEIGHTS = {
    "regime_conviction":     0.25,
    "structure_alignment":   0.20,
    "tf_confluence":         0.20,
    "liquidity_clear":       0.15,
    "vwap_context":          0.10,
    "macro_alignment":       0.10,
}

# ─── SESSION CONFIG ───────────────────────────────────────────────────────────
@dataclass
class SessionConfig:
    paper_trading:     bool  = PAPER_TRADING
    instrument:        str   = TRADING_SYMBOL
    notes:             str   = ""
    confirmed_at:      str   = ""
