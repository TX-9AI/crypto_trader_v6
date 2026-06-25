"""
config.py — Central configuration for the Crypto Adaptive Trading Bot
All parameters in one place. Tune here, not inside logic modules.

Credentials (API keys, tokens) are loaded from credentials.py.
Do not hardcode secrets in this file.

Instrument selection: uncomment ONE trading pair below.
Use configure.sh on EC2 to switch instruments without editing manually.
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

# ─── INSTRUMENT SELECTION ─────────────────────────────────────────────────────
# Uncomment ONE pair. Use configure.sh to switch without editing this file.

TRADING_SYMBOL = "BTC/USD"; KRAKEN_SYMBOL = "XBT/USD:BTNL"
# TRADING_SYMBOL = "ETH/USD"; KRAKEN_SYMBOL = "ETH/USD:BTNL"
# TRADING_SYMBOL = "SOL/USD"; KRAKEN_SYMBOL = "SOL/USD:BTNL"

# Derive short instrument name for display/alerts
INSTRUMENT                = TRADING_SYMBOL.split("/")[0]   # BTC, ETH, SOL

# ─── ACCOUNT & RISK ───────────────────────────────────────────────────────────

ACCOUNT_BALANCE_USD       = 2000.00
LEVERAGE                  = 10

RISK_PER_TRADE_USD        = 1.00          # $1 risk — minimum for diagnostic testing
CIRCUIT_BREAKER_PCT       = 0.25         # 25% of cash = rolling 24hr max loss
CIRCUIT_BREAKER_HOURS     = 24
CIRCUIT_BREAKER_MANUAL    = True

MAX_CONSECUTIVE_LOSSES    = 2
MAX_OPEN_RISK_PCT         = 1.00         # No cap — single position bot

# ─── POSITION SIZING MULTIPLIERS ──────────────────────────────────────────────

GRADE_SIZE_MULTIPLIER = {
    "A": 1.5,
    "B": 1.0,
    "C": 0.5,
}

TRADE_GRADE_C             = True

# ─── EXIT & PROFIT MANAGEMENT ─────────────────────────────────────────────────

TRAIL_ACTIVATION_R        = 1.0
TRAIL_STEP_1_R            = 1.0
TRAIL_STEP_2_R            = 2.0
TRAIL_STEP_3_R            = 3.0
TRAIL_TIGHTEN_ON_REGIME   = 0.25

PARTIAL_EXIT_PCT          = 0.50
PARTIAL_MINIMUM_R         = 0.75
STAGNANT_TRADE_MINUTES    = 120

# ─── REGIME CLASSIFICATION ────────────────────────────────────────────────────

ADX_TREND_THRESHOLD       = 25
ADX_RANGE_THRESHOLD       = 20
ATR_EXPANSION_MULTIPLIER  = 1.5
BB_WIDTH_COMPRESSION_PCT  = 0.20
SWEEP_REJECTION_CANDLES   = 3
EQUAL_LEVEL_PCT           = 0.001

# ─── REGIME REASSESSMENT ──────────────────────────────────────────────────────

REGIME_REASSESS_MINUTES   = 5
CONSECUTIVE_LOSS_REASSESS = True
COOLDOWN_AFTER_LOSS_MIN   = 0
ENTRY_COOLDOWN_MINUTES    = 0

# ─── SIGNAL VALIDATION ────────────────────────────────────────────────────────

MIN_TF_CONFLUENCE         = 1
LIQUIDITY_BUFFER_PCT      = 0.003
MIN_RRR                   = 1.0
VWAP_FILTER_ACTIVE        = False

# ─── SETUP SCORING WEIGHTS ────────────────────────────────────────────────────

SCORE_WEIGHTS = {
    "regime_conviction":     0.25,
    "structure_alignment":   0.20,
    "tf_confluence":         0.20,
    "liquidity_clear":       0.15,
    "vwap_context":          0.10,
    "macro_alignment":       0.10,
}

GRADE_A_MIN_SCORE         = 0.78
GRADE_B_MIN_SCORE         = 0.01

# ─── VOLATILITY ENGINE ────────────────────────────────────────────────────────

ATR_PERIOD                = 14
ATR_STOP_MULTIPLIER       = 0.1   # DIAGNOSTIC: ultra-tight stop, closes almost immediately
BB_PERIOD                 = 20
BB_STD                    = 2.0
VIX_LOW_THRESHOLD         = 15
VIX_ELEVATED_THRESHOLD    = 25
VIX_CRISIS_THRESHOLD      = 35
VIX_CRISIS_NO_LONG        = True

# ─── TREND ENGINE ─────────────────────────────────────────────────────────────

EMA_FAST                  = 9
EMA_MID                   = 21
EMA_SLOW                  = 50
EMA_ANCHOR                = 200

# ─── TIMEFRAMES ───────────────────────────────────────────────────────────────

TIMEFRAMES = {
    "1d":  {"ccxt": "1d",  "candles": 100, "role": "bias"},
    "4h":  {"ccxt": "4h",  "candles": 100, "role": "structure"},
    "1h":  {"ccxt": "1h",  "candles": 100, "role": "trend"},
    "15m": {"ccxt": "15m", "candles": 100, "role": "entry_context"},
    "5m":  {"ccxt": "5m",  "candles": 100, "role": "entry"},
    "1m":  {"ccxt": "1m",  "candles": 60,  "role": "trigger"},
}

CACHE_STALENESS_SECONDS = {
    "1d":  3600,
    "4h":  900,
    "1h":  300,
    "15m": 120,
    "5m":  30,
    "1m":  10,
}

# ─── KRAKEN API ───────────────────────────────────────────────────────────────

ORDER_TYPE_DEFAULT        = "market"
LIMIT_ORDER_SLIPPAGE_PCT  = 0.0005
MIN_ORDER_SIZE_BTC        = 0.0001

# ─── MACRO DATA ───────────────────────────────────────────────────────────────

MACRO_FETCH_INTERVAL_MIN  = 60
MACRO_ENABLED             = True

# ─── POLLING & TIMING ─────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS     = 10
TIMEZONE                  = "US/Eastern"

# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

NOTIFY_ON_ENTRY           = True
NOTIFY_ON_EXIT            = True
NOTIFY_ON_REGIME_CHANGE   = True
NOTIFY_PNL_UPDATE_MINUTES = 30
NOTIFY_CIRCUIT_BREAKER    = True
NOTIFY_CONSECUTIVE_LOSS   = True

# ─── DATABASE ─────────────────────────────────────────────────────────────────

DB_PATH                   = os.path.expanduser("~/crypto-trader/trades.db")

# ─── LOGGING ──────────────────────────────────────────────────────────────────

LOG_LEVEL                 = "INFO"
LOG_FILE                  = os.path.expanduser("~/crypto-trader/bot.log")
LOG_ROTATION_MB           = 50

# ─── STRUCTURE ANALYSIS ───────────────────────────────────────────────────────

SWING_LOOKBACK            = 10
MIN_SWING_SIZE_ATR        = 0.5
FVG_MIN_SIZE_PCT          = 0.001
SR_TOUCH_MIN              = 2
SR_ZONE_PCT               = 0.002

# ─── LIQUIDITY MAPPING ────────────────────────────────────────────────────────

EQUAL_HIGH_LOW_LOOKBACK   = 50
ORDER_BLOCK_LOOKBACK      = 20
IMBALANCE_MIN_SIZE_PCT    = 0.002

# ─── SESSION GUARD ────────────────────────────────────────────────────────────

TRADING_24_7              = True
BLACKOUT_WINDOWS          = []

# ─── PAPER TRADING ────────────────────────────────────────────────────────────
# Fresh deployments ALWAYS start in paper mode.
# Use configure.sh to switch to live trading.

PAPER_TRADING             = True
PAPER_FILL_SLIPPAGE_PCT   = 0.0003


@dataclass
class SessionConfig:
    """Runtime session config populated at startup."""
    paper_trading:     bool          = True
    risk_override_usd: float         = RISK_PER_TRADE_USD
    daily_loss_limit:  float         = ACCOUNT_BALANCE_USD * CIRCUIT_BREAKER_PCT
    notes:             str           = ""
    confirmed_at:      Optional[str] = None
