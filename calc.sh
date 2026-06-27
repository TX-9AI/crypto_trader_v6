#!/bin/bash
# calc.sh — Max Risk $ Calculator
# Shows the maximum RISK_PER_TRADE_USD you can safely set
# based on your account balance, leverage, and typical stop distance.

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$INSTALL_DIR"
source venv/bin/activate 2>/dev/null || true

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     Max Risk Dollar Calculator           ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  Instrument:"
echo "    1. BTC/USD"
echo "    2. ETH/USD"
echo "    3. SOL/USD"
echo ""
read -rp "  Select [1/2/3, default=1]: " INST_CHOICE
case "${INST_CHOICE:-1}" in
    2) SYMBOL="ETH/USD" ;;
    3) SYMBOL="SOL/USD" ;;
    *) SYMBOL="BTC/USD" ;;
esac

echo ""
echo "  Fetching live data for $SYMBOL..."
echo ""

python3 -c "
import sys; sys.path.insert(0, '.')
try:
    from data.market_data import get_account_balance, get_exchange
    import pandas as pd
    from config import LEVERAGE, ACCOUNT_BALANCE_USD, ATR_PERIOD

    bal  = get_account_balance()
    cash = bal['USD']['free'] if bal and bal.get('USD', {}).get('free', 0) > 0 else ACCOUNT_BALANCE_USD

    exchange      = get_exchange()
    ticker        = exchange.fetch_ticker('$SYMBOL')
    price         = ticker.get('last') or ticker.get('close') or 0
    if not price:
        print('  Could not fetch live price.')
        sys.exit(1)

    # Fetch ATR from 5m candles
    raw = exchange.fetch_ohlcv('$SYMBOL', '5m', limit=50)
    df  = pd.DataFrame(raw, columns=['ts','open','high','low','close','volume']).astype(float)
    hl  = df['high'] - df['low']
    hc  = (df['high'] - df['close'].shift()).abs()
    lc  = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(ATR_PERIOD).mean().iloc[-1]

    instrument   = '$SYMBOL'.split('/')[0]
    max_notional = cash * LEVERAGE
    max_contracts = max_notional / price

    # Risk = contracts × stop_distance
    # Stop = ATR × 1.5 (default multiplier)
    stop_dist    = atr * 1.5
    max_risk_usd = max_contracts * stop_dist

    print(f'  Account balance:  \${cash:,.2f}')
    print(f'  Leverage:         {LEVERAGE}x')
    print(f'  Live price:       \${price:,.2f}')
    print(f'  ATR (5m):         \${atr:,.4f}')
    print(f'  Stop distance:    \${stop_dist:,.4f}  (1.5x ATR)')
    print(f'  ─────────────────────────────────────────')
    print(f'  Max contracts:    {max_contracts:.4f} {instrument}')
    print(f'  Max RISK \$:       \${max_risk_usd:,.2f}')
    print(f'  ─────────────────────────────────────────')
    print(f'  → Set RISK_PER_TRADE_USD to \${max_risk_usd:,.2f} or less')
    print(f'    in configure.sh option 4.')

except Exception as e:
    print(f'  Error: {e}')
    import traceback; traceback.print_exc()
"
echo ""
