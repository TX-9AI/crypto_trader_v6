"""
test_telegram.py — Test Telegram bot connectivity.
Reads token and chat ID from environment variables (set by systemd).
Run: python test_telegram.py
"""

import os
import requests

token   = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    print("ERROR: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set.")
    print("Run as: TELEGRAM_TOKEN=<token> TELEGRAM_CHAT_ID=<id> python test_telegram.py")
    exit(1)

url  = f"https://api.telegram.org/bot{token}/sendMessage"
resp = requests.post(url, json={
    "chat_id":    chat_id,
    "text":       "✅ crypto_trader Telegram test — connected successfully.",
    "parse_mode": "HTML"
}, timeout=10)

if resp.status_code == 200:
    print("SUCCESS — message sent to Telegram.")
else:
    print(f"FAILED — {resp.status_code}: {resp.text}")
