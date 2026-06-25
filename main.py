"""
main.py — BTC Adaptive Trading Bot v1.0
Regime-aware, 24/7, institutional-grade.

Run modes:
  python main.py            — interactive startup prompt
  python main.py --service  — non-interactive for systemd
"""

import logging
import logging.handlers
import sys
import time
import traceback
from datetime import datetime
from typing import Optional

from config import (
    POLL_INTERVAL_SECONDS, LOG_LEVEL, LOG_FILE, LOG_ROTATION_MB,
    REGIME_REASSESS_MINUTES, PAPER_TRADING, ACCOUNT_BALANCE_USD,
    SessionConfig
)


def _setup_logging():
    root = logging.getLogger()
    if root.handlers:
        return
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_ROTATION_MB * 1024 * 1024, backupCount=5
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
    root.setLevel(level)


_setup_logging()
logger = logging.getLogger(__name__)

from utils.startup import run_startup_prompt
from utils.time_utils import now_utc, fmt_et_short, minutes_since

from data.data_cache import get_cache
from data.macro_data import get_macro_manager
from data.market_data import get_account_balance

from analysis.volatility_engine import get_volatility_engine
from analysis.trend_engine import get_trend_engine
from analysis.structure_analyzer import get_structure_analyzer
from analysis.liquidity_mapper import get_liquidity_mapper
from analysis.regime_classifier import get_regime_classifier, RegimeState

from strategy.strategy_selector import get_strategy_selector
from execution.signal_validator import get_signal_validator
from risk.setup_scorer import get_setup_scorer
from risk.risk_manager import init_risk_manager, get_risk_manager
from risk.session_guard import get_session_guard
from execution.entry_engine import get_entry_engine
from execution.position_manager import get_position_manager
from notifications.alert_manager import get_alert_manager
from database.db_manager import get_db


class BotState:
    def __init__(self):
        self.last_regime_at:   Optional[datetime] = None
        self.current_regime:   Optional[RegimeState] = None
        self.last_regime_name: str = "UNKNOWN"
        self.tick_count:       int = 0
        self.errors_this_hour: int = 0
        self.paper_trading:    bool = PAPER_TRADING
        # Whipsaw prevention: track last stop hit time and direction
        self.last_stop_hit_at:    Optional[datetime] = None
        self.last_stop_direction: str = ""
        self.regime_flip_candles: int = 0  # candles since last regime flip


def should_reassess_regime(state: BotState, consecutive_losses: int) -> tuple:
    if state.last_regime_at is None:
        return True, "initial"
    elapsed = minutes_since(state.last_regime_at)
    if elapsed >= REGIME_REASSESS_MINUTES:
        return True, "scheduled"
    if consecutive_losses >= 2:
        return True, "consecutive_loss"
    return False, ""


def run_analysis(state: BotState) -> dict:
    cache = get_cache()
    data  = cache.get_all()
    price = cache.get_price()
    if price is None:
        raise ValueError("Could not fetch current price")
    df_5m  = data.get("5m")
    df_15m = data.get("15m")
    df_1h  = data.get("1h")
    if df_5m is None or df_5m.empty:
        raise ValueError("No 5m data available")
    df_1h_safe = df_1h if df_1h is not None else df_5m
    vol_state = get_volatility_engine().analyze(df_5m, df_1h_safe, price)
    trend     = get_trend_engine().analyze(data)
    structure = get_structure_analyzer().analyze(df_5m, df_15m, df_1h, price)
    liq_map   = get_liquidity_mapper().analyze(df_5m, df_15m, price)
    macro     = get_macro_manager().get()
    return {
        "price":     price,
        "data":      data,
        "vol":       vol_state,
        "trend":     trend,
        "structure": structure,
        "liq_map":   liq_map,
        "macro":     macro,
    }


def run_regime_classification(ctx: dict, trigger: str, state: BotState) -> RegimeState:
    regime = get_regime_classifier().classify(
        vol_state=ctx["vol"],
        trend_state=ctx["trend"],
        structure=ctx["structure"],
        liq_map=ctx["liq_map"],
        macro=ctx["macro"],
        trigger=trigger
    )
    state.last_regime_at = now_utc()

    if regime.primary_regime != state.last_regime_name:
        logger.info(
            f"REGIME: {state.last_regime_name} → {regime.primary_regime} "
            f"(conviction={regime.conviction:.2f} trigger={trigger})"
        )
        # Only send email on genuine regime changes, not restarts
        if trigger != "initial":
            get_alert_manager().send_regime_alert(
                old_regime=state.last_regime_name,
                new_regime=regime.primary_regime,
                conviction=regime.conviction,
                trigger=trigger,
                notes=regime.notes
            )
        from database.trade_logger import get_trade_logger
        get_trade_logger().log_regime(
            regime=regime.primary_regime,
            conviction=regime.conviction,
            macro_context=ctx["macro"].macro_context if ctx["macro"] else "NEUTRAL",
            btc_personality=regime.btc_personality,
            adx=regime.adx,
            atr_norm=regime.atr_normalized,
            bb_width_pct=regime.bb_width_pct,
            session="see_vol",
            trigger=trigger
        )

    state.last_regime_name = regime.primary_regime
    state.current_regime   = regime
    return regime


def attempt_new_entry(ctx: dict, regime: RegimeState, state: BotState):
    risk_mgr  = get_risk_manager()
    session   = get_session_guard()
    validator = get_signal_validator()
    scorer    = get_setup_scorer()
    entry_eng = get_entry_engine(state.paper_trading)

    if not session.can_trade():
        logger.info("BLOCKED: session guard")
        return

    # Whipsaw prevention: after a stop hit, require 3 candle confirmation
    # before entering in the opposite direction (15 minutes on 5m chart)
    if (state.last_stop_hit_at is not None and
            state.last_stop_direction != ""):
        from utils.time_utils import minutes_since
        mins_since_stop = minutes_since(state.last_stop_hit_at)
        if mins_since_stop < 15:  # 3 x 5-minute candles
            logger.info(
                f"WHIPSAW GUARD: {mins_since_stop:.1f}min since stop hit "
                f"({state.last_stop_direction}) — blocking new entries for "                f"{15 - mins_since_stop:.1f}min more"
            )
            return

    signal = get_strategy_selector().generate_signal(
        regime=regime,
        vol_state=ctx["vol"],
        structure=ctx["structure"],
        liq_map=ctx["liq_map"],
        data=ctx["data"],
        current_price=ctx["price"]
    )

    if signal is None:
        logger.info(f"No signal from {get_strategy_selector().active_strategy_name}")
        return

    validation = validator.validate(
        signal=signal,
        regime=regime,
        vol_state=ctx["vol"],
        structure=ctx["structure"],
        liq_map=ctx["liq_map"],
        macro=ctx["macro"],
        data=ctx["data"],
        current_price=ctx["price"]
    )

    if not validation.passed:
        return

    score = scorer.score(
        signal=signal,
        regime=regime,
        vol_state=ctx["vol"],
        structure=ctx["structure"],
        liq_map=ctx["liq_map"],
        macro=ctx["macro"]
    )

    # Get live cash balance from Kraken
    live_bal = get_account_balance()
    cash_balance = live_bal["USD"]["free"] if live_bal else ACCOUNT_BALANCE_USD
    risk_mgr.update_cash_balance(cash_balance)

    sizing = risk_mgr.compute_size(
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        direction=signal.direction,
        grade=score.grade,
        grade_multiplier=score.size_multiplier,
        current_balance=cash_balance
    )

    if not sizing.allowed:
        logger.info(f"Sizing rejected: {sizing.reject_reason}")
        return

    record = entry_eng.enter(
        signal=signal,
        score=score,
        size_btc=sizing.size_btc,
        risk_usd=sizing.risk_usd,
        notional_usd=sizing.notional_usd
    )

    if record:
        record.regime_conviction = regime.conviction
        risk_mgr.add_open_risk(sizing.risk_usd)
        validator.record_entry(signal.direction)
        get_alert_manager().send_entry_alert(record)
        logger.info(f"Entry successful: {record.trade_id[:8]}")


def main_loop(state: BotState):
    pos_mgr = get_position_manager(state.paper_trading)

    while True:
        tick_start = time.time()
        state.tick_count += 1

        try:
            ctx = run_analysis(state)

            consec = get_risk_manager().consecutive_losses

            # Gate: only fire consecutive loss reassessment ONCE per event
            if consec == 0:
                state.reassessment_fired = False

            if consec >= 2 and not state.reassessment_fired:
                state.reassessment_fired = True
                should_reassess, trigger = True, "consecutive_loss"
            elif consec >= 2 and state.reassessment_fired:
                should_reassess, trigger = False, ""
            else:
                should_reassess, trigger = should_reassess_regime(state, consec)

            if should_reassess:
                regime = run_regime_classification(ctx, trigger, state)
                if trigger == "consecutive_loss":
                    get_risk_manager().reset_consecutive_losses()
                    get_signal_validator().reset_cooldown()
            else:
                regime = state.current_regime

            if regime is None:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            if pos_mgr.has_open_position():
                still_open = pos_mgr.manage_open_position(
                    current_price=ctx["price"],
                    structure=ctx["structure"],
                    current_regime=regime.primary_regime,
                    atr=ctx["vol"].atr_current
                )
                if still_open and state.tick_count % 180 == 0:
                    record = pos_mgr.get_open_record()
                    if record:
                        from utils.math_utils import r_multiple, unrealized_pnl
                        pnl = unrealized_pnl(
                            record["entry_price"], ctx["price"],
                            record["position_size"], record["direction"]
                        )
                        r = r_multiple(
                            record["entry_price"], ctx["price"],
                            record["stop_price"], record["direction"]
                        )
                        get_alert_manager().send_pnl_update(
                            trade_id=record["trade_id"],
                            direction=record["direction"],
                            entry_price=record["entry_price"],
                            current_price=ctx["price"],
                            current_r=r,
                            unrealized_pnl=pnl,
                            stop_price=record["stop_price"]
                        )
            else:
                attempt_new_entry(ctx, regime, state)

            if state.tick_count % 30 == 0:
                logger.info(
                    f"Tick #{state.tick_count} | "
                    f"price=${ctx['price']:,.2f} | "
                    f"regime={regime.primary_regime} ({regime.conviction:.0%}) | "
                    f"{get_risk_manager().status_report()}"
                )

            state.errors_this_hour = max(0, state.errors_this_hour - 1)

        except Exception as e:
            state.errors_this_hour += 1
            logger.error(f"Loop error (#{state.errors_this_hour}): {e}")
            logger.error(traceback.format_exc())
            if state.errors_this_hour > 30:
                logger.critical("Too many errors — shutting down")
                sys.exit(1)

        elapsed = time.time() - tick_start
        time.sleep(max(0, POLL_INTERVAL_SECONDS - elapsed))


def main():
    service_mode = "--service" in sys.argv

    if service_mode:
        live_bal = get_account_balance()
        cash_balance = live_bal["USD"]["free"] if live_bal else ACCOUNT_BALANCE_USD
        session_config = SessionConfig(
            paper_trading=PAPER_TRADING,
            notes="systemd auto-start"
        )
        logger.info(
            f"Service mode: {'PAPER' if PAPER_TRADING else 'LIVE'} | "
            f"cash=${cash_balance:,.2f} | "
            f"buying_power=${cash_balance * 10:,.2f}"
        )
    else:
        session_config = run_startup_prompt()
        live_bal = get_account_balance()
        cash_balance = live_bal["USD"]["free"] if live_bal else ACCOUNT_BALANCE_USD

    risk_mgr = init_risk_manager(session_config, cash_balance)
    get_db().initialize_schema()

    state = BotState()
    state.paper_trading = session_config.paper_trading

    logger.info(
        f"Bot initialized: {'PAPER' if state.paper_trading else 'LIVE'} | "
        f"cash=${cash_balance:,.2f} | "
        f"margin=${cash_balance * 10:,.2f} | "
        f"grade_A={cash_balance * 10 * 0.90:,.2f} | grade_B=${cash_balance * 10 * 0.75:,.2f}"
    )

    get_alert_manager().send_startup_alert(
        paper_trading=state.paper_trading,
        balance=cash_balance
    )

    logger.info("Fetching initial macro data...")
    get_macro_manager().get(force=True)

    logger.info(f"Starting main loop (poll={POLL_INTERVAL_SECONDS}s)")
    main_loop(state)


if __name__ == "__main__":
    main()
