"""
notifications/sms_sender.py — Telegram alert sender.
Replaces Twilio. Sends messages via Telegram Bot API.
Reads credentials from environment variables (set by systemd) first,
falls back to credentials.py if not found.
Gracefully disabled if not configured.
"""

import logging
import os
import requests

logger = logging.getLogger(__name__)


class SmsSender:
    def __init__(self):
        # Try environment variables first (set by systemd)
        token   = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        # Fall back to credentials.py
        if not token or not chat_id:
            try:
                from credentials import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                token   = token   or TELEGRAM_BOT_TOKEN
                chat_id = chat_id or TELEGRAM_CHAT_ID
            except (ImportError, AttributeError):
                pass

        self._token   = token
        self._chat_id = chat_id
        self._enabled = bool(self._token and self._chat_id)

        if self._enabled:
            logger.info(f"Telegram alerts enabled — chat_id={self._chat_id}")
        else:
            logger.info("Telegram alerts disabled — credentials not configured")

    def send(self, message: str) -> bool:
        if not self._enabled:
            logger.debug(f"Telegram (disabled): {message[:80]}")
            return False
        try:
            url  = f"https://api.telegram.org/bot{self._token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id":    self._chat_id,
                "text":       message,
                "parse_mode": "HTML"
            }, timeout=10)
            if resp.status_code == 200:
                logger.debug(f"Telegram sent: {message[:80]}")
                return True
            else:
                logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
